"""
verifier.py
-----------
The VERIFIER / CRITIC agent's logic. In the orchestrator-worker-verifier
pattern, the verifier is a second agent whose only job is to catch bad forecasts
BEFORE they are published. We keep its checks deterministic and testable so the
critic's verdicts are explainable (not a black box).

Checks per SKU (each can FLAG a forecast):
  V1  Non-positive forecast                 -> impossible
  V2  Above production/warehouse capacity     -> cannot be fulfilled
  V3  Wildly above recent history (> max_ratio x recent max) -> likely error
  V4  Collapsed vs history (< min_ratio x recent min)        -> likely error
  V5  Promo claimed but no uplift applied (or vice-versa)    -> inconsistent

A forecast set PASSES only if no SKU is flagged. Otherwise the verifier requests
rework and (via the event bus) raises a 'forecast.flagged' event.
"""
from dataclasses import dataclass, field
from typing import List, Dict

from tools import load_products, load_promotions, load_history

MAX_RATIO = 1.6    # forecast must not exceed 1.6x the recent weekly max
MIN_RATIO = 0.5    # forecast must not fall below 0.5x the recent weekly min
RECENT = 12        # weeks of history to compare against


@dataclass
class Flag:
    sku: str
    rule: str
    message: str


@dataclass
class VerifierReport:
    passed: bool
    flags: List[Flag] = field(default_factory=list)

    def as_dict(self):
        return {"passed": self.passed,
                "flags": [{"sku": f.sku, "rule": f.rule, "message": f.message} for f in self.flags]}


def verify(forecast: Dict[str, int]) -> VerifierReport:
    products = load_products()
    promos = load_promotions()["promotions"]
    history = load_history()
    flags: List[Flag] = []

    for sku, units in forecast.items():
        recent = history.get(sku, [])[-RECENT:]
        cap = products[sku]["capacity"]
        hi = max(recent) if recent else cap
        lo = min(recent) if recent else 0

        if units <= 0:
            flags.append(Flag(sku, "V1", f"Forecast {units} is non-positive."))
            continue
        if units > cap:
            flags.append(Flag(sku, "V2", f"Forecast {units} exceeds capacity {cap}."))
        if hi and units > MAX_RATIO * hi:
            flags.append(Flag(sku, "V3",
                              f"Forecast {units} is >{MAX_RATIO}x recent max {hi} — likely too high."))
        if lo and units < MIN_RATIO * lo:
            flags.append(Flag(sku, "V4",
                              f"Forecast {units} is <{MIN_RATIO}x recent min {lo} — likely too low."))
        # V5: promo/uplift consistency (forecast should be above recent average when on promo)
        if promos.get(sku) and recent:
            avg = sum(recent) / len(recent)
            if units < avg:
                flags.append(Flag(sku, "V5",
                                  f"SKU is on promo ({promos[sku]}% off) but forecast {units} "
                                  f"is below recent average {int(avg)} — uplift may be missing."))

    return VerifierReport(passed=(len(flags) == 0), flags=flags)


# ---------------------------------------------------------------------------
# Quality metric — so we can prove "cost down WITHOUT losing quality"
# ---------------------------------------------------------------------------
def mape(forecast: Dict[str, int]) -> float:
    """Mean Absolute Percentage Error vs held-out actuals. Lower is better."""
    from tools import load_actuals
    actuals = load_actuals()["actuals"]
    errs = []
    for sku, actual in actuals.items():
        if actual:
            errs.append(abs(forecast.get(sku, 0) - actual) / actual)
    return round(100 * sum(errs) / len(errs), 2) if errs else float("nan")


if __name__ == "__main__":
    # quick self-test: a good forecast passes, a broken one is flagged
    from tools import baseline_forecast, promo_uplift, reconcile, load_products
    skus = list(load_products())
    base = {s: baseline_forecast(s) for s in skus}
    upl = {s: promo_uplift(s) for s in skus}
    good = reconcile(base, upl)
    r = verify(good)
    print("good forecast passed:", r.passed, "| MAPE:", mape(good))
    bad = dict(good); bad[skus[0]] = 999999
    r2 = verify(bad)
    print("bad forecast passed:", r2.passed, "| flags:", [(f.sku, f.rule) for f in r2.flags])
    assert r.passed and not r2.passed
    print("verifier self-test: PASSED")

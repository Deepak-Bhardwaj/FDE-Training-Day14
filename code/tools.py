"""
tools.py
--------
The demand-planning tools. These are plain, deterministic Python functions that
BOTH the offline simulation and the real CrewAI agents call. Keeping the domain
logic here (not inside prompts) means the numbers are reproducible and testable.

  load_* ................ read the synthetic CPG data
  baseline_forecast ..... the Sales agent's job: forecast from history
  promo_uplift .......... the Promo agent's job: uplift from the promo calendar
  reconcile ............. the Orchestrator's job: combine baseline + uplift
"""
import csv, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))


def load_products():
    with open(os.path.join(DATA, "products.json")) as f:
        return json.load(f)


def load_promotions():
    with open(os.path.join(DATA, "promotions.json")) as f:
        return json.load(f)


def load_actuals():
    with open(os.path.join(DATA, "actuals.json")) as f:
        return json.load(f)


def load_history():
    """Return {sku: [units per week in order]}."""
    hist = defaultdict(list)
    with open(os.path.join(DATA, "sales_history.csv")) as f:
        for row in csv.DictReader(f):
            hist[row["sku"]].append(int(row["units"]))
    return dict(hist)


# ---------------------------------------------------------------------------
# Sales agent: baseline forecast (moving average + simple linear trend)
# ---------------------------------------------------------------------------
def baseline_forecast(sku: str, window: int = 8) -> int:
    hist = load_history()[sku]
    recent = hist[-window:]
    avg = sum(recent) / len(recent)
    # crude trend: average weekly change over the recent window
    diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
    trend = sum(diffs) / len(diffs) if diffs else 0
    return int(round(avg + trend))


# ---------------------------------------------------------------------------
# Promo agent: uplift for the target week from the promo calendar
# ---------------------------------------------------------------------------
def promo_uplift(sku: str) -> dict:
    products = load_products()
    promos = load_promotions()["promotions"]
    discount = promos.get(sku, 0)
    sensitivity = products[sku]["promo_sensitivity"]
    factor = 1 + (discount / 100.0) * sensitivity if discount else 1.0
    return {"sku": sku, "discount_pct": discount, "uplift_factor": round(factor, 3)}


# ---------------------------------------------------------------------------
# Orchestrator: reconcile baseline + promo into a final forecast per SKU
# ---------------------------------------------------------------------------
def reconcile(baseline: dict, uplift: dict) -> dict:
    """baseline: {sku: units}, uplift: {sku: {uplift_factor,...}} -> {sku: units}."""
    out = {}
    for sku, base in baseline.items():
        f = uplift.get(sku, {}).get("uplift_factor", 1.0)
        out[sku] = int(round(base * f))
    return out

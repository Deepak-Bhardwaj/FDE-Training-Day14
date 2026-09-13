"""
pipeline.py
-----------
The orchestrator-worker-verifier PATTERN, framework-agnostic and deterministic,
so it runs and can be tested offline. The real CrewAI crew (crew_demand_planner.py)
performs the same steps with LLM agents; this module lets you exercise the
ORCHESTRATION logic (events, verifier, rework loop, cost) without an LLM.

Flow (one 'decision'):
  1. sales_agent   -> baseline forecast per SKU          [worker, parallel-able]
  2. promo_agent   -> uplift per SKU                      [worker, parallel-able]
  3. orchestrator  -> reconcile baseline + uplift         [orchestrator]
  4. verifier      -> sanity-check; if flagged, request rework, cap to capacity,
                      and re-verify                        [verifier / critic]
  5. publish forecast.approved (or forecast.flagged)      [via Service Bus]

Every step publishes an event to the bus, so a scaled-out consumer could react.
"""
from typing import Callable, Dict, Optional

from tools import load_products, baseline_forecast, promo_uplift, reconcile
from verifier import verify, mape
from service_bus import get_bus, LocalBus
from cost import estimate_run_cost, ROUTED


class DemandPlanner:
    def __init__(self, bus=None, agent_models: Dict[str, str] = None,
                 fault: "Optional[Fault]" = None):
        self.bus = bus if bus is not None else LocalBus()
        self.agent_models = agent_models or ROUTED
        self.fault = fault                     # chaos hook (None in normal runs)
        self.events = []

    def _emit(self, etype, payload):
        self.bus.publish(etype, payload)
        self.events.append(etype)

    # --- workers -----------------------------------------------------------
    def run_sales_agent(self, skus):
        if self.fault:
            self.fault.maybe("sales_timeout")
        base = {s: baseline_forecast(s) for s in skus}
        if self.fault:
            base = self.fault.maybe_corrupt("bad_sales_data", base)
        self._emit("baseline.created", {"skus": len(base)})
        return base

    def run_promo_agent(self, skus):
        upl = {s: promo_uplift(s) for s in skus}
        self._emit("uplift.created", {"skus": len(upl)})
        return upl

    # --- orchestrator + verifier ------------------------------------------
    def plan(self) -> dict:
        skus = list(load_products())
        baseline = self.run_sales_agent(skus)
        uplift = self.run_promo_agent(skus)

        forecast = reconcile(baseline, uplift)
        self._emit("forecast.created", {"n": len(forecast)})

        report = verify(forecast)
        reworked = False
        if not report.passed:
            self._emit("forecast.flagged", {"flags": report.as_dict()["flags"]})
            # Rework: the orchestrator caps any over-capacity SKU and asks workers
            # to trust history where a value looks broken, then re-verifies.
            forecast = self._rework(forecast)
            report = verify(forecast)
            reworked = True

        etype = "forecast.approved" if report.passed else "forecast.rejected"
        self._emit(etype, {"passed": report.passed})

        cost = estimate_run_cost(self.agent_models)
        return {
            "forecast": forecast,
            "verifier": report.as_dict(),
            "reworked": reworked,
            "mape": mape(forecast),
            "cost_per_decision_usd": round(cost.total_usd, 4),
            "events": list(self.events),
            "final_status": etype,
        }

    def _rework(self, forecast: dict) -> dict:
        """Deterministic rework: cap to capacity, replace absurd values with a
        history-based baseline. This is what the critic->orchestrator loop does."""
        products = load_products()
        fixed = dict(forecast)
        for sku, units in forecast.items():
            cap = products[sku]["capacity"]
            base = baseline_forecast(sku)
            if units <= 0 or units > 1.6 * max(base, 1) * 1.6:
                fixed[sku] = base                      # clearly broken -> trust history
            fixed[sku] = min(fixed[sku], cap)          # never exceed capacity
        self._emit("rework.requested", {"skus": len(fixed)})
        return fixed


def run_once(bus=None, agent_models=None, fault=None) -> dict:
    planner = DemandPlanner(bus=bus, agent_models=agent_models, fault=fault)
    return planner.plan()


if __name__ == "__main__":
    import json
    result = run_once()
    print(json.dumps({k: v for k, v in result.items() if k != "forecast"}, indent=2))
    print("forecast:", result["forecast"])

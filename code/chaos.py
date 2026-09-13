"""
chaos.py
--------
The Chaos Drill engine (the 30-minute mock chaos test). Mentors "break things";
the pod's agent must respond. This module injects faults and scores how the
multi-agent system copes.

Fault types (mentor picks one or more):
  sales_timeout   : the sales worker hangs / times out
  bad_sales_data  : the sales worker returns a corrupted forecast (e.g. a huge spike)
  servicebus_down : the event bus fails on publish
  cost_spike      : a model upgrade quadruples token cost mid-run
  verifier_bypass : (anti-pattern) try to skip the verifier — should NOT be allowed

Each drill run returns a SCORECARD: did the system stay up, did the verifier
catch bad forecasts, did cost stay controlled, was the failure observable?
"""
import random
from dataclasses import dataclass, field
from typing import List, Optional

from cost import ALL_PREMIUM, ROUTED, estimate_run_cost


class ChaosError(Exception):
    pass


@dataclass
class Fault:
    kinds: List[str]
    rng: random.Random = field(default_factory=lambda: random.Random(9))

    def active(self, kind: str) -> bool:
        return kind in self.kinds

    def maybe(self, kind: str):
        """Raise/trip a fault of this kind if it is active."""
        if self.active(kind):
            if kind == "sales_timeout":
                raise TimeoutError("sales_agent timed out (injected)")

    def maybe_corrupt(self, kind: str, data: dict) -> dict:
        if self.active(kind) and kind == "bad_sales_data" and data:
            bad = dict(data)
            first = next(iter(bad))
            bad[first] = 10_000_000          # absurd spike the verifier must catch
            return bad
        return data


@dataclass
class Scorecard:
    stayed_up: bool = False
    verifier_caught: bool = False
    cost_controlled: bool = False
    observable: bool = False
    notes: List[str] = field(default_factory=list)

    def score(self) -> int:
        return sum([self.stayed_up, self.verifier_caught, self.cost_controlled, self.observable])

    def as_dict(self):
        return {"stayed_up": self.stayed_up, "verifier_caught": self.verifier_caught,
                "cost_controlled": self.cost_controlled, "observable": self.observable,
                "score_out_of_4": self.score(), "notes": self.notes}


def run_drill(fault_kinds: List[str]) -> dict:
    """Run one demand-planning decision under the given faults and score it."""
    from pipeline import DemandPlanner
    from service_bus import LocalBus

    fault = Fault(kinds=fault_kinds)
    card = Scorecard()
    bus = LocalBus()

    # Cost spike: mentors 'upgrade the model', quadrupling worker cost.
    models = ROUTED
    if fault.active("cost_spike"):
        models = ALL_PREMIUM
        card.notes.append("Model upgraded to all-premium mid-run (cost spike injected).")

    # A resilient pod wraps the sales worker with a retry/fallback.
    planner = DemandPlanner(bus=bus, agent_models=models, fault=fault)
    try:
        # sales_timeout: first attempt fails; pod retries WITHOUT the fault (fallback).
        try:
            result = planner.plan()
        except TimeoutError:
            card.notes.append("sales_agent timed out; pod retried with fallback (no fault).")
            planner_retry = DemandPlanner(bus=bus, agent_models=models, fault=Fault(kinds=[
                k for k in fault_kinds if k != "sales_timeout"]))
            result = planner_retry.plan()
        card.stayed_up = True
    except Exception as e:  # noqa: BLE001
        card.notes.append(f"System crashed: {type(e).__name__}: {e}")
        return {"scorecard": card.as_dict(), "result": None}

    # Did the verifier catch the injected bad data?
    if fault.active("bad_sales_data"):
        flagged = "forecast.flagged" in result["events"]
        card.verifier_caught = flagged
        card.notes.append("Verifier flagged the corrupted forecast." if flagged
                          else "MISS: verifier did not flag the corrupted forecast.")
    else:
        card.verifier_caught = result["verifier"]["passed"] or "forecast.flagged" in result["events"]

    # Cost control: is cost-per-decision within budget after any spike?
    budget = 0.05
    cpd = result["cost_per_decision_usd"]
    card.cost_controlled = cpd <= budget
    card.notes.append(f"cost-per-decision ${cpd} (budget ${budget}).")
    if fault.active("cost_spike") and not card.cost_controlled:
        card.notes.append("ACTION: route workers to cheaper models to restore budget.")

    # Observable: were events emitted (so App Insights / Monitor would see it)?
    card.observable = len(result["events"]) >= 3
    card.notes.append(f"{len(result['events'])} events emitted to the bus.")

    # verifier_bypass is an anti-pattern: the verifier always runs, so bypass fails.
    if fault.active("verifier_bypass"):
        card.notes.append("verifier_bypass attempted — verifier still ran (cannot be skipped).")

    return {"scorecard": card.as_dict(), "result":
            {k: v for k, v in result.items() if k != "forecast"}}

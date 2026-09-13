"""
cost.py
-------
Token accounting and the CRO's number: COST PER DECISION.

A "decision" here = one demand-planning run (the crew produces a verified
forecast set for the target week). Cost-per-decision = total token cost of that
run.

This module answers two scenario questions:
  1. "Token costs jumped 4x overnight after a model upgrade. Bring them down in
      24h without losing quality." -> compare an all-premium config against a
      ROUTED config (cheap models for workers, premium only where it matters).
  2. "The CRO wants a cost-per-decision number in 1 hour." -> cost_per_decision().

Prices are approximate USD per 1,000,000 tokens and are easy to edit. Treat them
as teaching values, not a live price list — always confirm current Azure pricing.
"""
from dataclasses import dataclass
from typing import Dict

# Approx USD per 1M tokens (input, output). EDIT to match your Azure pricing.
MODEL_PRICES = {
    "gpt-4o":        {"in": 2.50, "out": 10.00},
    "gpt-4o-mini":   {"in": 0.15, "out": 0.60},
    "gpt-4.1":       {"in": 2.00, "out": 8.00},
    "gpt-4.1-mini":  {"in": 0.40, "out": 1.60},
    "o4-mini":       {"in": 1.10, "out": 4.40},
}

# Typical tokens each agent uses in one run (input+output), from usage_metrics.
# These are illustrative defaults; the real numbers come from Crew.usage_metrics.
DEFAULT_TOKENS = {
    "sales_agent":   {"in": 3500, "out": 700},
    "promo_agent":   {"in": 3200, "out": 600},
    "orchestrator":  {"in": 5000, "out": 1200},
    "verifier":      {"in": 4200, "out": 900},
}


@dataclass
class RunCost:
    total_usd: float
    per_agent: Dict[str, float]

    def as_dict(self):
        return {"cost_per_decision_usd": round(self.total_usd, 4),
                "per_agent_usd": {k: round(v, 4) for k, v in self.per_agent.items()}}


def _agent_cost(model: str, tokens: dict) -> float:
    p = MODEL_PRICES[model]
    return tokens["in"] / 1_000_000 * p["in"] + tokens["out"] / 1_000_000 * p["out"]


def estimate_run_cost(agent_models: Dict[str, str], tokens: Dict[str, dict] = None) -> RunCost:
    """agent_models: {agent_name: model}. tokens: per-agent token counts."""
    tokens = tokens or DEFAULT_TOKENS
    per_agent = {a: _agent_cost(m, tokens.get(a, {"in": 0, "out": 0}))
                 for a, m in agent_models.items()}
    return RunCost(total_usd=sum(per_agent.values()), per_agent=per_agent)


def cost_per_decision(agent_models: Dict[str, str], tokens: Dict[str, dict] = None) -> float:
    return estimate_run_cost(agent_models, tokens).total_usd


# ---------------------------------------------------------------------------
# The scenarios
# ---------------------------------------------------------------------------
ALL_PREMIUM = {a: "gpt-4o" for a in DEFAULT_TOKENS}
ROUTED = {  # cheap models for the routine workers, premium only for reasoning
    "sales_agent": "gpt-4o-mini",
    "promo_agent": "gpt-4o-mini",
    "orchestrator": "gpt-4o",       # reconciliation needs the stronger model
    "verifier": "gpt-4o-mini",      # verifier checks are mostly deterministic
}


def scenario_report(monthly_decisions: int = 20000) -> dict:
    premium = estimate_run_cost(ALL_PREMIUM)
    routed = estimate_run_cost(ROUTED)
    saving = 1 - (routed.total_usd / premium.total_usd) if premium.total_usd else 0
    return {
        "all_premium_per_decision": round(premium.total_usd, 4),
        "routed_per_decision": round(routed.total_usd, 4),
        "saving_pct": round(100 * saving, 1),
        "all_premium_monthly": round(premium.total_usd * monthly_decisions, 2),
        "routed_monthly": round(routed.total_usd * monthly_decisions, 2),
        "monthly_saving": round((premium.total_usd - routed.total_usd) * monthly_decisions, 2),
    }


if __name__ == "__main__":
    import json
    print("All-premium per decision:", cost_per_decision(ALL_PREMIUM))
    print("Routed per decision     :", cost_per_decision(ROUTED))
    print(json.dumps(scenario_report(), indent=2))

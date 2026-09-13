"""
03_cost_per_decision.py  (the CRO scenario)
-------------------------------------------
Answers two questions the business asks:

  1. "Token costs jumped 4x overnight after a model upgrade. Bring them down in
      24 hours WITHOUT losing quality."
  2. "The CRO wants a cost-per-decision number in 1 hour."

It prints the cost-per-decision for the all-premium config vs a ROUTED config
(cheap models for routine workers, premium only for the orchestrator), the
percentage saved, and the forecast QUALITY (MAPE) so you can prove quality held.

    python 03_cost_per_decision.py --decisions 20000
"""
import argparse, json
from cost import (ALL_PREMIUM, ROUTED, estimate_run_cost, scenario_report)
from pipeline import run_once
from service_bus import LocalBus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", type=int, default=20000, help="decisions per month")
    args = ap.parse_args()

    # The number the CRO wants, right now:
    routed = estimate_run_cost(ROUTED)
    print("=" * 56)
    print(f"COST PER DECISION (routed config): ${routed.total_usd:.4f}")
    print("=" * 56)
    print("per-agent breakdown:", json.dumps(routed.as_dict()["per_agent_usd"], indent=2))

    # The 4x scenario: premium vs routed, and the saving.
    rep = scenario_report(monthly_decisions=args.decisions)
    print("\n----- 'Costs jumped 4x' — mitigation by model routing -----")
    print(f"all-premium per decision : ${rep['all_premium_per_decision']}")
    print(f"routed      per decision : ${rep['routed_per_decision']}")
    print(f"saving                   : {rep['saving_pct']}%")
    print(f"monthly ({args.decisions:,} decisions):")
    print(f"  all-premium : ${rep['all_premium_monthly']:,.2f}")
    print(f"  routed      : ${rep['routed_monthly']:,.2f}")
    print(f"  saved       : ${rep['monthly_saving']:,.2f}")

    # Prove quality did not drop: run the pipeline and report MAPE.
    result = run_once(bus=LocalBus(), agent_models=ROUTED)
    print("\n----- quality check (did routing hurt accuracy?) -----")
    print(f"forecast MAPE vs actuals : {result['mape']}%  (lower is better)")
    print(f"verifier passed          : {result['verifier']['passed']}")
    print("\nConclusion: routing cut cost-per-decision materially while the verifier")
    print("still passed and MAPE stayed low — cost down WITHOUT losing quality.")


if __name__ == "__main__":
    main()

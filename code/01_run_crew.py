"""
01_run_crew.py  (LAB 9-A)
-------------------------
Run the multi-agent demand planner (orchestrator + workers + verifier/critic).

    python 01_run_crew.py --mock     # offline deterministic pipeline (no Azure)
    python 01_run_crew.py            # real CrewAI crew on Azure OpenAI (needs .env)

--mock runs pipeline.py (same pattern, deterministic). Without --mock it runs the
real CrewAI crew from crew_demand_planner.py.
"""
import argparse, json
from dotenv import load_dotenv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="offline deterministic pipeline")
    args = ap.parse_args()
    load_dotenv()

    if args.mock:
        from pipeline import run_once
        from service_bus import get_bus
        bus = get_bus(prefer_azure=False)   # --mock is offline: always use LocalBus
        result = run_once(bus=bus)
        print("\n----- DEMAND PLAN (mock pipeline) -----")
        print("final status :", result["final_status"])
        print("reworked     :", result["reworked"])
        print("MAPE vs actuals:", result["mape"], "%")
        print("cost/decision : $", result["cost_per_decision_usd"])
        print("events        :", result["events"])
        print("\nverifier report:")
        print(json.dumps(result["verifier"], indent=2))
        print("\nforecast:")
        print(json.dumps(result["forecast"], indent=2))
    else:
        from crew_demand_planner import run_crew
        out = run_crew()
        print("\n----- CREW RESULT -----")
        print(out["result"])
        print("\n----- TOKEN USAGE (for cost-per-decision) -----")
        print(json.dumps(out["usage_metrics"], indent=2))


if __name__ == "__main__":
    main()

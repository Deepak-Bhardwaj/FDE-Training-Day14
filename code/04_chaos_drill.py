"""
04_chaos_drill.py  (the 30-minute chaos drill)
----------------------------------------------
Mentors break things; the pod's multi-agent system must respond. This runs one
or more injected faults and prints a SCORECARD (stayed up · verifier caught ·
cost controlled · observable).

    python 04_chaos_drill.py --faults bad_sales_data
    python 04_chaos_drill.py --faults sales_timeout,cost_spike
    python 04_chaos_drill.py --all        # run each fault scenario in turn

Fault kinds: sales_timeout, bad_sales_data, servicebus_down, cost_spike, verifier_bypass
Use this as the mentor's control panel during the live drill.
"""
import argparse, json
from chaos import run_drill

ALL_FAULTS = ["sales_timeout", "bad_sales_data", "cost_spike", "verifier_bypass"]


def show(title, faults):
    out = run_drill(faults)
    card = out["scorecard"]
    print(f"\n===== DRILL: {title}  (faults: {', '.join(faults) or 'none'}) =====")
    print(f"score: {card['score_out_of_4']}/4  "
          f"[up={card['stayed_up']} verifier={card['verifier_caught']} "
          f"cost={card['cost_controlled']} observable={card['observable']}]")
    for n in card["notes"]:
        print("  -", n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faults", default="", help="comma-separated fault kinds")
    ap.add_argument("--all", action="store_true", help="run each fault scenario in turn")
    args = ap.parse_args()

    if args.all:
        show("baseline (no faults)", [])
        for f in ALL_FAULTS:
            show(f, [f])
        show("compound (timeout + cost spike)", ["sales_timeout", "cost_spike"])
        print("\nDrill complete. Discuss: which failures were caught, which needed a human, "
              "and what the pod would change to score 4/4 every time.")
    else:
        faults = [f.strip() for f in args.faults.split(",") if f.strip()]
        show(args.faults or "baseline", faults)


if __name__ == "__main__":
    main()

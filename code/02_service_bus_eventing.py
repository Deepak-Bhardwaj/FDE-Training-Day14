"""
02_service_bus_eventing.py  (LAB 9-B)
-------------------------------------
Wire inter-agent eventing through Azure Service Bus. The planner PUBLISHES events
as it works; a separate consumer READS them and reacts (e.g. a notifier pod, or a
scaled-out worker). This is the decoupling that lets each agent scale out.

    python 02_service_bus_eventing.py --local     # in-memory bus (offline)
    python 02_service_bus_eventing.py             # real Azure Service Bus (needs .env)

With Azure, run a producer in one terminal and a consumer in another; the queue
carries events between them and survives restarts.
"""
import argparse, json
from dotenv import load_dotenv

from pipeline import run_once
from service_bus import get_bus, LocalBus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="force the in-memory bus")
    ap.add_argument("--role", choices=["both", "produce", "consume"], default="both")
    args = ap.parse_args()
    load_dotenv()

    bus = LocalBus() if args.local else get_bus()

    if args.role in ("both", "produce"):
        print("[producer] running a demand-planning decision and publishing events...")
        result = run_once(bus=bus)
        print("[producer] published events:", result["events"])
        print("[producer] final status:", result["final_status"])

    if args.role in ("both", "consume"):
        print("\n[consumer] reading events off the bus and reacting:")
        for msg in bus.receive():
            etype, payload = msg["type"], msg["payload"]
            action = {
                "forecast.flagged": "-> alert planners: verifier rejected a forecast",
                "forecast.approved": "-> publish the plan to the S&OP system",
                "rework.requested": "-> re-run the affected worker",
            }.get(etype, "-> log for audit")
            print(f"  event {etype:18} {action}")

    print("\nNote: with real Azure Service Bus, the producer and consumer can run in "
          "separate processes/pods and the queue carries events between them.")


if __name__ == "__main__":
    main()

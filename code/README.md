# Lab 9 — Code

Multi-agent **demand planner** (CPG) with an orchestrator, two workers, and a
**verifier/critic** agent — plus Azure Service Bus eventing, a cost-per-decision
model, and a chaos drill.

Full instructions: `Lab9_Multi_Agent_Setup_Steps.docx`.
Interpreting results: `Lab9_Outcomes_Interpretation.docx`.

## Files

| File | Role |
|------|------|
| `generate_cpg_data.py` | Build the synthetic CPG dataset (run once) |
| `tools.py` | Forecasting logic: baseline, promo uplift, reconcile |
| `verifier.py` | The critic's deterministic checks + MAPE quality metric |
| `pipeline.py` | Orchestrator-worker-verifier flow (offline, deterministic) |
| `crew_demand_planner.py` | The **real CrewAI crew** on Azure OpenAI (Lab 9-A) |
| `service_bus.py` | Azure Service Bus eventing + in-memory `LocalBus` (Lab 9-B) |
| `cost.py` | Token pricing + **cost-per-decision** + routing scenario |
| `chaos.py` | Chaos-drill engine (fault injection + scorecard) |
| `01_run_crew.py` | **Lab 9-A** run the multi-agent planner |
| `02_service_bus_eventing.py` | **Lab 9-B** publish/consume inter-agent events |
| `03_cost_per_decision.py` | The CRO's number + "costs jumped 4x" mitigation |
| `04_chaos_drill.py` | **Drill** inject faults, print a scorecard |
| `test_offline.py` | Runs the whole thing offline and asserts every path |

## Quick start

```bash
# Apple Silicon (macOS): the system python3 is usually x86_64, and crewai's
# lancedb dependency ships NO x86_64-macOS wheel -> `pip install` fails with
# "No matching distribution found for lancedb". Build the venv with a native
# arm64 Python via uv instead:
#     uv python install 3.12
#     uv venv --python 3.12 .venv && source .venv/bin/activate
#     uv pip install -r requirements.txt
# On the Azure VM (Linux) — the delivery target — the plain commands below work as-is:

python -m venv .venv && source .venv/bin/activate     # separate venv from Labs 7/8
pip install -r requirements.txt
python generate_cpg_data.py

# Offline — no Azure, no CrewAI LLM calls:
python test_offline.py
python 01_run_crew.py --mock
python 02_service_bus_eventing.py --local
python 03_cost_per_decision.py
python 04_chaos_drill.py --all

# Azure — fill in .env first:
cp .env.example .env
python 01_run_crew.py                 # real CrewAI crew on Azure OpenAI
python 02_service_bus_eventing.py     # real Azure Service Bus
```

## The pattern

`orchestrator-worker-verifier`: two workers (sales baseline, promo uplift) feed an
orchestrator that reconciles a forecast; a **verifier/critic** flags bad forecasts
before they are published. Agents are decoupled through **Service Bus events**.

> The CPG data is **synthetic** teaching data.

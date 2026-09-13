# FDE Training Day 14: Multi-Agent Orchestration Lab

## 🎯 Objective
This repository contains the code and artifacts for the FORGE FDE Academy Day 14 lab on **Multi-Agent Orchestration**. The lab implements an enterprise-grade CPG Demand Planner using the **Orchestrator-Worker-Verifier** pattern, backed by Azure Service Bus for eventing and resilience engineering.

## 🏗️ Architecture & Topology
The system implements a hybrid multi-agent pattern on Azure:
- **Orchestrator:** Plans, routes, and reconciles tasks (kept thin to avoid bottlenecks).
- **Workers (Sales Baseline & Promo Uplift):** Pull data and generate raw SKU-level forecasts.
- **Verifier (Critic):** A deterministic agent that checks forecasts against 5 specific rules (V1-V5: capacity, historical bounds, promo consistency) before publishing.

## ☁️ Azure Eventing & Resilience
Agents are decoupled using **Azure Service Bus** (simulated via `LocalBus` for offline testing) to ensure scale-out and reliability:
- **Queues (Competing Consumers):** Used for horizontal scaling of worker agents.
- **Peek-Lock & DLQ:** Ensures at-least-once delivery and quarantines "poison messages" after `MaxDeliveryCount` failures.

## 📂 Repository Structure
- **Core Engine:**
  - `crew_demand_planner.py`: The real CrewAI crew definition.
  - `verifier.py`: The deterministic critic (Rules V1-V5).
  - `tools.py`, `pipeline.py`, `cost.py`: Forecasting logic, orchestrator flow, and token pricing models.
  - `service_bus.py`: Azure Service Bus eventing + in-memory `LocalBus`.
  - `chaos.py`: Chaos-drill engine (fault injection + scorecard).
- **Lab Execution Scripts:**
  - `01_run_crew.py`: **Lab 9-A** Runs the multi-agent planner.
  - `02_service_bus_eventing.py`: **Lab 9-B** Publishes/consumes inter-agent events.
  - `03_cost_per_decision.py`: Evaluates cost-per-decision and routing scenarios.
  - `04_chaos_drill.py`: **Drill** Injects faults and prints a resilience scorecard.
  - `test_offline.py`: Runs the entire pipeline offline to assert all paths.
- **Data & Docs:**
  - `generate_cpg_data.py`: Builds the synthetic CPG dataset.
  - `/diagram`: Architecture and topology diagrams.
  - `Lab9_*.docx` & `Lab9_*.pdf`: Official setup steps, outcome interpretations, and Chaos Studio walkthroughs.

## 🧪 Chaos Drill Scenarios
The chaos engine injects specific faults to validate graceful degradation:
- `sales_timeout`: Worker fails to respond (tests timeouts/fallbacks).
- `bad_sales_data`: Poisoned data (tests Verifier V1-V5 rules).
- `cost_spike`: Runaway token usage (tests cost guardrails).
- `verifier_bypass`: Attempts to skip the critic (tests security/flow integrity).

- ## 🧪 Chaos Drill Execution Results
Executed locally via `python 04_chaos_drill.py --all`. 

| Scenario | Score | Key Observation |
| :--- | :---: | :--- |
| **Baseline** | 4/4 | Cost: $0.0275. System stable. |
| **sales_timeout** | 4/4 | Orchestrator retried with fallback. Graceful degradation. |
| **bad_sales_data** | 4/4 | Verifier flagged corrupted forecast. Routed to DLQ (6 events emitted). |
| **cost_spike** | 3/4 | Cost hit $0.0737 (Budget $0.05). Requires model-tiering guardrail. |
| **verifier_bypass** | 4/4 | Bypass attempted, but Verifier was forced to run. Flow integrity intact. |
| **compound** | 3/4 | Timeout handled, but cost spike still breached budget. |

**Architectural Takeaway:** The system successfully contained cascading failures, caught poison data, and prevented verifier bypasses. To achieve a consistent 4/4, the pod must implement automated model-tiering (downgrading to cheaper LLMs) when cost guardrails are breached.

---
*Confidential · FORGE FDE Academy · Multi-Agent Orchestration*

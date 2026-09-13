# FDE Training Day 14: Multi-Agent Orchestration Lab

## 🎯 Objective
This repository contains the artifacts and code for the FORGE FDE Academy Day 14 lab on Multi-Agent Orchestration. The goal was to design, execute, and stress-test a resilient multi-agent system for CPG Demand Planning.

## 🏗️ Architecture & Topology
The system implements a hybrid multi-agent pattern:
- **Orchestrator:** Plans, routes, and reconciles tasks (kept thin to avoid bottlenecks).
- **Workers (Sales/Data):** Pull data from SAP/Databricks and generate raw forecasts.
- **Verifier (Judge):** Acts as an exception-finder, rejecting anomalous data (e.g., pending sales) before it reaches the final plan.

## ☁️ Azure Eventing & Resilience
Agents are decoupled using **Azure Service Bus** to ensure scale-out and reliability:
- **Queues:** Used for competing consumers (horizontal scaling of worker agents).
- **Peek-Lock:** Ensures at-least-once delivery; if an agent crashes, the message returns to the queue.
- **Dead-Letter Queue (DLQ):** Quarantines "poison messages" after `MaxDeliveryCount` failures, preventing pipeline hangs.

## 🧪 Chaos Drill Results
A deliberate fault was injected to validate graceful degradation:
- **Inject:** Poisoned the Service Bus queue with a payload containing `pending_orders > 0`.
- **Observe:** The Verifier agent rejected the payload based on its strict backstory rules.
- **Verify:** The message safely routed to the DLQ after retries, and the Orchestrator flagged the gap without crashing the overall workflow.

## 📂 Repository Structure
- `code/`: Agent implementation and orchestration logic.
- `data/`: Sample payloads and test data.
- `diagram/`: Architecture and topology diagrams.
- `Lab9_*.docx` / `Lab9_*.pdf`: Official training setup steps, outcome interpretations, and Chaos Studio portal walkthroughs.

---
*Confidential · FORGE FDE Academy · Multi-Agent Orchestration*

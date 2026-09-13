"""
crew_demand_planner.py  (LAB 9-A — the real CrewAI crew)
--------------------------------------------------------
The multi-agent demand planner built with CrewAI and Azure OpenAI. This is the
"real Azure" path; the offline pipeline.py mirrors the same steps deterministically.

Agents (orchestrator-worker-verifier pattern):
  Sales Analyst   (worker)       -> baseline_forecast tool
  Promo Modeler   (worker)       -> promo_uplift tool
  Demand Planner  (orchestrator) -> reconcile tool, combines the two
  Verifier Critic (verifier)     -> verify tool, flags bad forecasts

Azure OpenAI via CrewAI needs these env vars (see .env.example):
  AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
and a chat deployment name passed as model="azure/<deployment>".
CrewAI 1.15.1 routes "azure/<deployment>" through its native Azure provider
(the crewai[azure-ai-inference] extra), which reads the same env vars above.

Run:
    python 01_run_crew.py            # this file is imported by 01_run_crew.py
"""
import json
import os


def build_crew(deployment: str = None):
    """Construct the CrewAI crew. Imports crewai lazily so offline code is unaffected."""
    from crewai import Agent, Task, Crew, Process, LLM
    from crewai.tools import tool

    import tools as T

    deployment = deployment or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    # CrewAI talks to Azure through LiteLLM using the "azure/<deployment>" model id.
    llm = LLM(model=f"azure/{deployment}", temperature=0.1)

    # --- tools the agents may call (thin wrappers over the deterministic logic) ---
    @tool("baseline_forecast")
    def t_baseline(sku: str) -> str:
        """Return the baseline unit forecast for a SKU from sales history."""
        return json.dumps({"sku": sku, "baseline": T.baseline_forecast(sku)})

    @tool("promo_uplift")
    def t_uplift(sku: str) -> str:
        """Return the promo uplift factor for a SKU for the target week."""
        return json.dumps(T.promo_uplift(sku))

    @tool("list_skus")
    def t_skus() -> str:
        """List all SKUs to plan for."""
        return json.dumps(list(T.load_products().keys()))

    sales_analyst = Agent(
        role="Sales Analyst",
        goal="Produce an accurate baseline forecast per SKU from historical sales.",
        backstory="You read sales history and project next week's baseline demand.",
        tools=[t_skus, t_baseline], llm=llm, allow_delegation=False, verbose=True)

    promo_modeler = Agent(
        role="Promotion Modeler",
        goal="Estimate the demand uplift from planned promotions per SKU.",
        backstory="You quantify how discounts lift demand using promo sensitivity.",
        tools=[t_skus, t_uplift], llm=llm, allow_delegation=False, verbose=True)

    planner = Agent(
        role="Demand Planner (Orchestrator)",
        goal="Reconcile baseline and promo uplift into a single forecast per SKU.",
        backstory="You combine the analysts' inputs into one defensible plan.",
        llm=llm, allow_delegation=False, verbose=True)

    verifier = Agent(
        role="Verifier Critic",
        goal="Catch bad forecasts: over-capacity, implausible spikes, missing uplift.",
        backstory="You are the last line of defence before a forecast is published. "
                  "You flag anything that looks wrong and demand a rework.",
        llm=llm, allow_delegation=False, verbose=True)

    t1 = Task(description="List the SKUs, then give the baseline forecast for each.",
              expected_output="A JSON object mapping each SKU to its baseline units.",
              agent=sales_analyst)
    t2 = Task(description="For each SKU, compute the promo uplift factor for the target week.",
              expected_output="A JSON object mapping each SKU to its uplift factor.",
              agent=promo_modeler)
    t3 = Task(description="Reconcile baseline x uplift into a final forecast per SKU.",
              expected_output="A JSON object mapping each SKU to final forecast units.",
              agent=planner, context=[t1, t2])
    t4 = Task(description="Verify the final forecast. Flag any SKU that exceeds capacity, "
                          "is implausibly high/low, or is on promo but shows no uplift. "
                          "State PASS or FAIL with reasons.",
              expected_output="A verdict (PASS/FAIL) with a list of flagged SKUs and reasons.",
              agent=verifier, context=[t3])

    crew = Crew(agents=[sales_analyst, promo_modeler, planner, verifier],
                tasks=[t1, t2, t3, t4], process=Process.sequential, verbose=True)
    return crew


def run_crew():
    crew = build_crew()
    result = crew.kickoff(inputs={"target_week": 105})
    usage = getattr(crew, "usage_metrics", None)
    return {"result": str(result), "usage_metrics": usage.model_dump() if usage else None}

"""Multi-agent procurement decision system.

Root coordinator -> Data Analyst, Knowledge, Research, Critic, Decision agents.
Agents communicate through shared session state (evidence, findings, critique, brief)
via validated tools, not through free text alone.
"""

from os import environ

from google.adk import Agent

from ai_template_python.rate_limit import pace_model_calls, retry_config
from ai_template_python.tools.analytics.investigation_state import (
    check_findings,
    list_findings,
    record_critique,
    record_finding,
    submit_decision_brief,
)
from ai_template_python.tools.market_data.commodity_trend import get_commodity_trend
from ai_template_python.tools.rag.document_search import search_documents
from ai_template_python.tools.sql.contract_terms import get_contract_terms
from ai_template_python.tools.sql.spend_analysis import analyze_supplier_monthly_spend

DEFAULT_MODEL = "gemini-flash-latest"

_FINDING_RULES = (
    "Record each key result with record_finding, citing only evidence IDs returned by your "
    "tools. Use kind=fact only for directly observed values; interpretations are assessments. "
    "Always add a caveat when data is synthetic or a proxy. Do all record_finding calls in "
    "one step, then reply with a two-sentence summary."
)


def _specialist(name: str, model: str, description: str, instruction: str, tools: list) -> Agent:
    return Agent(
        name=name,
        model=model,
        description=description,
        mode="single_turn",
        instruction=f"{instruction} {_FINDING_RULES}",
        tools=tools,
        before_model_callback=pace_model_calls,
        generate_content_config=retry_config(),
    )


def create_decision_system(model: str | None = None) -> Agent:
    """Build the coordinator with its five-agent specialist team."""
    selected = model or environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    data_analyst = _specialist(
        "data_analyst",
        selected,
        "Quantifies supplier spend from purchase-order data using SQL.",
        "You are the procurement Data Analyst. Call analyze_supplier_monthly_spend for the "
        "supplier and period requested. Report the largest absolute month-over-month change "
        "with currency and months. Use agent='data_analyst' when recording findings.",
        [analyze_supplier_monthly_spend, record_finding],
    )
    knowledge_agent = _specialist(
        "knowledge_agent",
        selected,
        "Finds contract terms and procurement-policy rules relevant to the question.",
        "You are the Knowledge Agent. Call get_contract_terms for the supplier, then "
        "search_documents (document_type='contract' with the supplier_id, and "
        "document_type='policy') for price-adjustment clauses and approval rules. Quote only "
        "what the results state. Use agent='knowledge_agent' when recording findings.",
        [get_contract_terms, search_documents, record_finding],
    )
    research_agent = _specialist(
        "research_agent",
        selected,
        "Retrieves external commodity price context from World Bank data.",
        "You are the Research Agent. For an industrial-components supplier, call "
        "get_commodity_trend for aluminum, copper and zinc over a window covering the period "
        "plus six prior months. Market indices are context, not proof of a supplier's cost; say "
        "so. Use agent='research_agent' when recording findings.",
        [get_commodity_trend, record_finding],
    )
    critic_agent = Agent(
        name="critic_agent",
        model=selected,
        description="Challenges findings: checks support, contradictions and evidence quality.",
        mode="single_turn",
        instruction=(
            "You are the Critic. Do not produce your own answer. Call list_findings and "
            "check_findings, then judge whether each claim is supported by the cited evidence "
            "excerpts, whether findings contradict each other, whether a market trend is wrongly "
            "presented as proof of a supplier price rise, and whether synthetic data is "
            "disclosed. Finish with exactly one record_critique call: needs_more_evidence if a "
            "material gap exists, approved_with_caveats if only caveats remain, otherwise "
            "approved. Then reply in two sentences."
        ),
        tools=[list_findings, check_findings, record_critique],
        before_model_callback=pace_model_calls,
        generate_content_config=retry_config(),
    )
    decision_agent = Agent(
        name="decision_agent",
        model=selected,
        description="Writes the evidence-cited decision brief after the Critic's review.",
        mode="single_turn",
        instruction=(
            "You are the Decision Agent. Call list_findings, then call submit_decision_brief "
            "once. Keep verified_facts strictly to kind=fact findings, each ending with its "
            "finding ID like [F2]; put interpretation in assessment and the action in "
            "recommendation (which needs human approval). Carry over the Critic's caveats as "
            "uncertainties. Do not add claims absent from the findings. If submit_decision_brief "
            "is refused, report why. Then reply in two sentences."
        ),
        tools=[list_findings, submit_decision_brief],
        before_model_callback=pace_model_calls,
        generate_content_config=retry_config(),
    )

    return Agent(
        name="procurement_coordinator",
        model=selected,
        description="Coordinates a multi-agent procurement investigation.",
        instruction=(
            "You coordinate an investigation by delegating, in this order: data_analyst, "
            "knowledge_agent, research_agent, critic_agent, decision_agent. Give each a short "
            "self-contained request with the supplier ID and dates. If critic_agent returns "
            "needs_more_evidence, delegate one targeted follow-up to the relevant specialist, "
            "then re-run critic_agent once. Never invent figures; do the work only through "
            "delegation. Call each specialist at most once, and stop delegating as soon as "
            "decision_agent has run. Your final answer must only restate decision_agent's "
            "brief (headline, recommendation, confidence, uncertainties); do not add your own "
            "recommendation, never recommend approval, and say it needs human approval. Cite "
            "evidence IDs only if decision_agent reported them. Under 150 words."
        ),
        sub_agents=[data_analyst, knowledge_agent, research_agent, critic_agent, decision_agent],
        before_model_callback=pace_model_calls,
        generate_content_config=retry_config(),
    )


decision_system = create_decision_system()

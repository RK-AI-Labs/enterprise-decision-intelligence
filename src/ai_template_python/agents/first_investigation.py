"""First ADK coordinator/Data Analyst investigation workflow."""

from os import environ

from google.adk import Agent

from ai_template_python.tools.sql.spend_analysis import analyze_supplier_monthly_spend

DEFAULT_MODEL = "gemini-flash-latest"


def create_investigation_agents(model: str | None = None) -> tuple[Agent, Agent]:
    """Build the coordinator and its single-turn procurement Data Analyst."""
    selected_model = model or environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    data_analyst = Agent(
        name="data_analyst",
        model=selected_model,
        description="Analyzes tenant-scoped supplier purchase-order spend using SQL.",
        mode="single_turn",
        instruction=(
            "You are the procurement Data Analyst. For supplier spend questions, call "
            "analyze_supplier_monthly_spend with the supplier ID and inclusive date range. "
            "Never invent values or request tenant IDs. Report currency, the largest absolute "
            "change between consecutive calendar months, and the underlying months and amounts. "
            "Distinguish missing data from zero spend. State when the returned data is synthetic."
        ),
        tools=[analyze_supplier_monthly_spend],
    )
    root = Agent(
        name="root_agent",
        model=selected_model,
        description="Coordinates procurement investigations and presents evidence-based findings.",
        instruction=(
            "You coordinate procurement investigations. Delegate supplier-spend analysis to "
            "the data_analyst. Base conclusions only on the specialist's returned evidence. "
            "Summarize the finding, figures, currency, evidence period, synthetic-data caveat, "
            "and any uncertainty. Do not claim that purchase-order values are paid invoices."
        ),
        sub_agents=[data_analyst],
    )
    return root, data_analyst


root_agent, data_analyst_agent = create_investigation_agents()

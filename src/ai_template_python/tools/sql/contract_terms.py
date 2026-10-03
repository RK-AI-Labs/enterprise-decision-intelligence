"""Read-only, tenant-scoped contract lookup for the Knowledge Agent."""

from os import environ
from typing import Any
from uuid import UUID

import psycopg
from google.adk.tools import ToolContext

from ai_template_python.evidence import register_evidence

_CONTRACT_SQL = """
SELECT contracts.contract_id, contracts.title, contracts.start_date, contracts.end_date,
       contracts.annual_value_gbp, contracts.price_adjustment_cap_percent,
       contracts.is_synthetic
FROM contracts
WHERE contracts.tenant_id = %s AND contracts.supplier_id = %s
ORDER BY contracts.start_date DESC
"""


def get_contract_terms(supplier_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return structured contract terms (value, dates, price-adjustment cap) for a supplier.

    Args:
        supplier_id: Supplier identifier, for example S102.
    """
    tenant_value = tool_context.state.get("tenant_id")
    if not tenant_value:
        return {"status": "error", "message": "Authorized tenant context is missing."}
    try:
        tenant_id = UUID(str(tenant_value))
    except ValueError:
        return {"status": "error", "message": "Tenant ID is invalid."}
    supplier = supplier_id.strip()
    if not supplier or len(supplier) > 100:
        return {"status": "error", "message": "Supplier ID is invalid."}
    database_url = environ.get("DATABASE_URL")
    if not database_url:
        return {"status": "error", "message": "DATABASE_URL is not configured."}

    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            rows = connection.execute(_CONTRACT_SQL, (tenant_id, supplier)).fetchall()
    except psycopg.Error:
        return {"status": "error", "message": "The contract query could not be completed."}
    if not rows:
        return {"status": "success", "supplier_id": supplier, "contracts": []}

    contracts = []
    for contract_id, title, start, end, value, cap, is_synthetic in rows:
        summary = (
            f"{contract_id}: {start}..{end}, annual value GBP {value}, price adjustment cap {cap}%"
        )
        evidence_id = register_evidence(
            tool_context.state,
            source_type="database",
            source_id=contract_id,
            locator=f"contracts:{supplier}:{contract_id}",
            citation_label=f"Contract record {contract_id}",
            excerpt=summary,
            is_synthetic=is_synthetic,
        )
        contracts.append(
            {
                "evidence_id": evidence_id,
                "contract_id": contract_id,
                "title": title,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "annual_value_gbp": str(value),
                "price_adjustment_cap_percent": str(cap),
                "is_synthetic": is_synthetic,
            }
        )
    return {"status": "success", "supplier_id": supplier, "contracts": contracts}

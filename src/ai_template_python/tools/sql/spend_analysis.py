"""Read-only, tenant-scoped supplier spend analysis tool for ADK."""

from datetime import date
from decimal import Decimal
from os import environ
from typing import Any
from uuid import UUID

import psycopg
from google.adk.tools import ToolContext

_MONTHLY_SPEND_SQL = """
WITH monthly_spend AS (
    SELECT
        date_trunc('month', purchase_orders.ordered_on)::date AS month,
        purchase_orders.currency::text AS currency,
        SUM(purchase_order_items.line_total)::numeric(18, 2) AS spend,
        COUNT(DISTINCT purchase_orders.purchase_order_id)::integer AS purchase_order_count,
        bool_and(purchase_orders.is_synthetic) AS is_synthetic
    FROM purchase_orders
    JOIN purchase_order_items
      ON purchase_order_items.tenant_id = purchase_orders.tenant_id
     AND purchase_order_items.purchase_order_id = purchase_orders.purchase_order_id
    WHERE purchase_orders.tenant_id = %s
      AND purchase_orders.supplier_id = %s
      AND purchase_orders.ordered_on >= %s
      AND purchase_orders.ordered_on <= %s
      AND purchase_orders.status IN ('issued', 'invoiced')
    GROUP BY 1, 2
)
SELECT month, currency, spend, purchase_order_count, is_synthetic
FROM monthly_spend
ORDER BY currency, month
"""


def analyze_supplier_monthly_spend(
    supplier_id: str,
    start_date: str,
    end_date: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Return monthly purchase-order spend and the largest adjacent-month change.

    Args:
        supplier_id: Supplier identifier, for example S102.
        start_date: Inclusive ISO date (YYYY-MM-DD).
        end_date: Inclusive ISO date (YYYY-MM-DD).
        tool_context: ADK context containing the tenant ID established by the caller.
    """
    tenant_value = tool_context.state.get("tenant_id")
    if not tenant_value:
        return {"status": "error", "message": "Authorized tenant context is missing."}

    try:
        tenant_id = UUID(str(tenant_value))
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Tenant ID or date input is invalid."}

    if start > end:
        return {"status": "error", "message": "start_date must be on or before end_date."}
    if (end - start).days > 366 * 5:
        return {"status": "error", "message": "Date range cannot exceed five years."}
    if not supplier_id.strip() or len(supplier_id) > 100:
        return {"status": "error", "message": "Supplier ID is invalid."}

    database_url = environ.get("DATABASE_URL")
    if not database_url:
        return {"status": "error", "message": "DATABASE_URL is not configured."}

    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            rows = connection.execute(
                _MONTHLY_SPEND_SQL,
                (tenant_id, supplier_id.strip(), start, end),
            ).fetchall()
    except psycopg.Error:
        return {"status": "error", "message": "The spend query could not be completed."}

    monthly: list[dict[str, object]] = []
    largest_change: dict[str, str] | None = None
    largest_change_magnitude = Decimal("-1")
    previous_by_currency: dict[str, tuple[date, Decimal]] = {}

    for month, currency, spend, purchase_order_count, is_synthetic in rows:
        amount = Decimal(spend)
        month_label = month.isoformat()
        monthly.append(
            {
                "month": month_label,
                "currency": currency,
                "spend": str(amount),
                "purchase_order_count": purchase_order_count,
                "is_synthetic": is_synthetic,
            }
        )

        previous = previous_by_currency.get(currency)
        if previous is not None:
            previous_month, previous_amount = previous
            month_index = month.year * 12 + month.month
            previous_index = previous_month.year * 12 + previous_month.month
            if month_index == previous_index + 1:
                change = amount - previous_amount
                magnitude = abs(change)
                if magnitude > largest_change_magnitude:
                    largest_change_magnitude = magnitude
                    percentage = change / previous_amount * 100 if previous_amount != 0 else None
                    largest_change = {
                        "month": month_label,
                        "currency": currency,
                        "amount_change": str(change),
                        "percentage_change": (
                            str(percentage.quantize(Decimal("0.01")))
                            if percentage is not None
                            else "undefined (prior month was zero)"
                        ),
                    }
        previous_by_currency[currency] = (month, amount)

    return {
        "status": "success",
        "supplier_id": supplier_id.strip(),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "monthly_spend": monthly,
        "largest_month_over_month_change": largest_change,
        "largest_change_is_absolute_amount": True,
        "data_note": "Purchase-order line totals; draft and cancelled orders are excluded.",
    }

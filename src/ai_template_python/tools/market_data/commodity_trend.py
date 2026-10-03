"""Read-only external commodity price trends (World Bank Pink Sheet) for the Research Agent."""

from datetime import date
from decimal import Decimal
from os import environ
from typing import Any

import psycopg
from google.adk.tools import ToolContext

from ai_template_python.evidence import register_evidence

_SERIES_SQL = """
SELECT observed_on, value, unit, source_name, source_url
FROM commodity_observations
WHERE series_id = %s AND observed_on >= %s AND observed_on <= %s
ORDER BY observed_on
"""


def get_commodity_trend(
    series_id: str, start_date: str, end_date: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Return a monthly commodity price series and its change over the period.

    Args:
        series_id: World Bank series such as aluminum, copper, zinc, nickel, iron-ore-cfr-spot.
        start_date: Inclusive ISO date (YYYY-MM-DD).
        end_date: Inclusive ISO date (YYYY-MM-DD).
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return {"status": "error", "message": "Date input is invalid."}
    series = series_id.strip().lower()
    if not series or len(series) > 100 or start > end or (end - start).days > 366 * 10:
        return {"status": "error", "message": "Series ID or date range is invalid."}
    database_url = environ.get("DATABASE_URL")
    if not database_url:
        return {"status": "error", "message": "DATABASE_URL is not configured."}

    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            rows = connection.execute(_SERIES_SQL, (series, start, end)).fetchall()
    except psycopg.Error:
        return {"status": "error", "message": "The market-data query could not be completed."}
    if not rows:
        return {"status": "error", "message": f"No observations for series '{series}'."}

    first, last = rows[0], rows[-1]
    first_value, last_value = Decimal(first[1]), Decimal(last[1])
    percentage = (
        ((last_value - first_value) / first_value * 100).quantize(Decimal("0.01"))
        if first_value != 0
        else None
    )
    peak = max(rows, key=lambda row: row[1])
    summary = (
        f"{series} ({first[2]}): {first[0]} {first_value} -> {last[0]} {last_value}; "
        f"change {percentage}%; peak {peak[1]} on {peak[0]}"
    )
    evidence_id = register_evidence(
        tool_context.state,
        source_type="external",
        source_id=f"{first[3]}:{series}",
        locator=f"commodity_observations:{series}:{start}..{end}",
        citation_label=f"{first[3]} {series} monthly price",
        excerpt=summary,
        is_synthetic=False,
    )
    return {
        "status": "success",
        "evidence_id": evidence_id,
        "series_id": series,
        "unit": first[2],
        "source": first[3],
        "observations": len(rows),
        "first": {"date": first[0].isoformat(), "value": str(first_value)},
        "last": {"date": last[0].isoformat(), "value": str(last_value)},
        "peak": {"date": peak[0].isoformat(), "value": str(peak[1])},
        "percentage_change": str(percentage),
        "monthly_values": [{"date": row[0].isoformat(), "value": str(row[1])} for row in rows],
    }

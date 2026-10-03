from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from ai_template_python.tools.sql import spend_analysis

TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.query: str | None = None
        self.parameters: tuple[Any, ...] | None = None

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, parameters: tuple[Any, ...]) -> FakeConnection:
        self.query = query
        self.parameters = parameters
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


def test_spend_tool_scopes_query_and_finds_largest_adjacent_month_change(
    monkeypatch: Any,
) -> None:
    connection = FakeConnection(
        [
            (date(2025, 6, 1), "GBP", Decimal("100.00"), 2, True),
            (date(2025, 7, 1), "GBP", Decimal("115.00"), 2, True),
            (date(2025, 9, 1), "GBP", Decimal("500.00"), 3, True),
        ]
    )
    monkeypatch.setattr(spend_analysis, "environ", {"DATABASE_URL": "postgresql://test"})
    monkeypatch.setattr(spend_analysis.psycopg, "connect", lambda *args, **kwargs: connection)
    context = SimpleNamespace(state={"tenant_id": str(TENANT_ID)})

    result = spend_analysis.analyze_supplier_monthly_spend(
        "S102", "2025-06-01", "2025-09-30", context
    )

    assert result["status"] == "success"
    assert result["monthly_spend"][0]["spend"] == "100.00"
    assert result["largest_month_over_month_change"] == {
        "month": "2025-07-01",
        "currency": "GBP",
        "amount_change": "15.00",
        "percentage_change": "15.00",
    }
    assert connection.parameters == (
        TENANT_ID,
        "S102",
        date(2025, 6, 1),
        date(2025, 9, 30),
    )
    assert "tenant_id = %s" in connection.query
    assert "supplier_id = %s" in connection.query
    assert "S102" not in connection.query


def test_spend_tool_requires_authorized_tenant_before_database_access(monkeypatch: Any) -> None:
    def fail_if_connected(*args: object, **kwargs: object) -> None:
        raise AssertionError("database must not be contacted without tenant context")

    monkeypatch.setattr(spend_analysis.psycopg, "connect", fail_if_connected)

    result = spend_analysis.analyze_supplier_monthly_spend(
        "S102", "2025-06-01", "2025-09-30", SimpleNamespace(state={})
    )

    assert result == {"status": "error", "message": "Authorized tenant context is missing."}

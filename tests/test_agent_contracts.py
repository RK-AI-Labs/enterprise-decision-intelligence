from datetime import date

import pytest

from ai_template_python.contracts import (
    DocumentSearchRequest,
    DocumentSearchResult,
    SpendAnalysisRequest,
    ToolError,
    ToolResult,
    VarianceAnalysisRequest,
)
from ai_template_python.state import new_investigation_state


def test_tool_result_requires_exactly_one_outcome() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ToolResult()

    with pytest.raises(ValueError, match="exactly one"):
        ToolResult(data={"rows": 1}, error=ToolError("failure", "safe", False))


def test_document_search_bounds_results_and_requires_types() -> None:
    with pytest.raises(ValueError, match="top_k"):
        DocumentSearchRequest("contract", ("contract",), top_k=21)

    with pytest.raises(ValueError, match="document type"):
        DocumentSearchRequest("contract", ())

    with pytest.raises(ValueError, match="unsupported type"):
        DocumentSearchRequest("contract", ("unsupported",))  # type: ignore[arg-type]


def test_empty_document_search_is_distinct_from_unconfigured_corpus() -> None:
    no_matches = DocumentSearchResult(corpus_version="corpus-v1", documents=())
    unavailable = ToolResult(error=ToolError("SOURCE_NOT_CONFIGURED", "Not available", False))

    assert no_matches.documents == ()
    assert no_matches.corpus_version == "corpus-v1"
    assert unavailable.error is not None
    assert unavailable.error.code == "SOURCE_NOT_CONFIGURED"


def test_variance_rejects_zero_baseline() -> None:
    with pytest.raises(ValueError, match="non-zero"):
        VarianceAnalysisRequest(0, 10, "USD")


def test_investigation_state_is_initialized_with_schema_version() -> None:
    state = new_investigation_state(
        investigation_id="inv-1",
        tenant_id="tenant-1",
        requester_id="user-1",
        question=" Why did spend increase? ",
    )

    assert state["schema_version"] == 1
    assert state["question"] == "Why did spend increase?"
    assert state["status"] == "queued"
    assert state["evidence"] == []


def test_spend_query_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="on or before"):
        SpendAnalysisRequest(date(2026, 2, 1), date(2026, 1, 1))

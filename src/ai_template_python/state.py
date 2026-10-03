"""Versioned, JSON-serializable working state for one investigation."""

from typing import Literal, TypedDict


class TaskState(TypedDict):
    task_id: str
    agent: Literal["data_analyst", "knowledge", "research", "critic", "decision"]
    objective: str
    status: Literal["pending", "running", "completed", "failed", "blocked"]
    depends_on: list[str]


class EvidencePointer(TypedDict):
    evidence_id: str
    source_type: Literal["database", "document", "external"]
    source_id: str
    locator: str
    observed_at: str
    content_sha256: str | None


class Finding(TypedDict):
    finding_id: str
    statement: str
    kind: Literal["fact", "assessment", "recommendation"]
    evidence_ids: list[str]
    confidence: Literal["low", "medium", "high"]
    caveats: list[str]


class ApprovalRequest(TypedDict):
    approval_id: str
    reason: str
    action_summary: str
    evidence_ids: list[str]
    status: Literal["pending", "approved", "rejected", "expired"]
    requested_at: str
    decided_at: str | None
    decided_by: str | None
    rationale: str | None


class InvestigationState(TypedDict):
    schema_version: int
    investigation_id: str
    tenant_id: str
    requester_id: str
    question: str
    status: Literal[
        "queued",
        "investigating",
        "validating",
        "awaiting_human",
        "completed",
        "failed",
    ]
    tasks: list[TaskState]
    findings: list[Finding]
    evidence: list[EvidencePointer]
    event_ids: list[str]
    unresolved_questions: list[str]
    approvals: list[ApprovalRequest]
    decision_brief: dict[str, object] | None


def new_investigation_state(
    *,
    investigation_id: str,
    tenant_id: str,
    requester_id: str,
    question: str,
) -> InvestigationState:
    """Create the minimal initial state after API authorization succeeds."""
    if not question.strip():
        raise ValueError("question must not be empty")

    return {
        "schema_version": 1,
        "investigation_id": investigation_id,
        "tenant_id": tenant_id,
        "requester_id": requester_id,
        "question": question.strip(),
        "status": "queued",
        "tasks": [],
        "findings": [],
        "evidence": [],
        "event_ids": [],
        "unresolved_questions": [],
        "approvals": [],
        "decision_brief": None,
    }

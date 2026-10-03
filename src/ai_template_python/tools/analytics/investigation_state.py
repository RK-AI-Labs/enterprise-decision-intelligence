"""Shared-state tools: findings, critique, and the final decision brief.

Agents never write state directly; these tools validate every write so that evidence
references, critique status, and the brief stay consistent.
"""

from typing import Any, Literal

from google.adk.tools import ToolContext

from ai_template_python.evidence import BRIEF_KEY, CRITIQUE_KEY, EVIDENCE_KEY, FINDINGS_KEY

_KINDS = ("fact", "assessment", "recommendation")
_CONFIDENCE = ("low", "medium", "high")
_VERDICTS = ("approved", "approved_with_caveats", "needs_more_evidence")
REQUIRED_CONTRIBUTORS = ("data_analyst", "knowledge_agent", "research_agent")


def _evidence_by_id(tool_context: ToolContext) -> dict[str, dict[str, Any]]:
    return {item["evidence_id"]: item for item in tool_context.state.get(EVIDENCE_KEY) or []}


def record_finding(
    agent: str,
    statement: str,
    kind: Literal["fact", "assessment", "recommendation"],
    evidence_ids: list[str],
    confidence: Literal["low", "medium", "high"],
    caveats: list[str],
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Record one finding in the shared investigation state.

    Args:
        agent: Your agent name, for example data_analyst, knowledge_agent, research_agent.
        statement: One self-contained claim, including figures and units.
        kind: fact (directly observed), assessment (interpretation) or recommendation.
        evidence_ids: Evidence IDs (E1, E2...) returned by tools that support the claim.
        confidence: low, medium or high.
        caveats: Known limitations, for example synthetic data or proxy series.
    """
    if kind not in _KINDS or confidence not in _CONFIDENCE or not statement.strip():
        return {"status": "error", "message": "Invalid kind, confidence, or empty statement."}
    known = _evidence_by_id(tool_context)
    unknown = [item for item in evidence_ids if item not in known]
    if unknown:
        return {"status": "error", "message": f"Unknown evidence IDs: {unknown}"}
    if kind == "fact" and not evidence_ids:
        return {"status": "error", "message": "A fact must cite at least one evidence ID."}

    findings = list(tool_context.state.get(FINDINGS_KEY) or [])
    finding_id = f"F{len(findings) + 1}"
    findings.append(
        {
            "finding_id": finding_id,
            "agent": agent,
            "statement": statement.strip(),
            "kind": kind,
            "evidence_ids": list(evidence_ids),
            "confidence": confidence,
            "caveats": list(caveats),
        }
    )
    tool_context.state[FINDINGS_KEY] = findings
    return {"status": "success", "finding_id": finding_id}


def list_findings(tool_context: ToolContext) -> dict[str, Any]:
    """Return all findings and the evidence records they cite, for review."""
    return {
        "status": "success",
        "findings": tool_context.state.get(FINDINGS_KEY) or [],
        "evidence": [
            {key: value for key, value in item.items() if key != "content_sha256"}
            for item in tool_context.state.get(EVIDENCE_KEY) or []
        ],
    }


def check_findings(tool_context: ToolContext) -> dict[str, Any]:
    """Run deterministic evidence-quality checks over all findings (Critic tool)."""
    findings = tool_context.state.get(FINDINGS_KEY) or []
    known = _evidence_by_id(tool_context)
    issues: list[str] = []
    contributors = {finding.get("agent") for finding in findings}

    for finding in findings:
        finding_id = finding["finding_id"]
        cited = [known[e] for e in finding["evidence_ids"] if e in known]
        if finding["kind"] == "fact" and not cited:
            issues.append(f"{finding_id}: fact has no evidence.")
        if finding["kind"] == "recommendation" and not cited:
            issues.append(f"{finding_id}: recommendation cites no evidence.")
        if finding["confidence"] == "high" and finding["kind"] != "fact" and len(cited) < 2:
            issues.append(f"{finding_id}: high-confidence {finding['kind']} has <2 sources.")
        if cited and all(item.get("is_synthetic") for item in cited) and not finding["caveats"]:
            issues.append(f"{finding_id}: relies on synthetic data but states no caveat.")

    issues.extend(
        f"No findings from {name}; coverage is incomplete."
        for name in REQUIRED_CONTRIBUTORS
        if name not in contributors
    )
    return {
        "status": "success",
        "finding_count": len(findings),
        "evidence_count": len(known),
        "automated_issues": issues,
    }


def record_critique(
    verdict: Literal["approved", "approved_with_caveats", "needs_more_evidence"],
    issues: list[str],
    requested_follow_ups: list[str],
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Store the Critic's verdict.

    Args:
        verdict: approved, approved_with_caveats, or needs_more_evidence.
        issues: Unsupported claims, contradictions, or weak evidence that you found.
        requested_follow_ups: Specific extra investigation needed, empty if none.
    """
    if verdict not in _VERDICTS:
        return {"status": "error", "message": f"verdict must be one of {_VERDICTS}"}
    tool_context.state[CRITIQUE_KEY] = {
        "verdict": verdict,
        "issues": list(issues),
        "requested_follow_ups": list(requested_follow_ups),
    }
    return {"status": "success", "verdict": verdict}


def submit_decision_brief(
    headline: str,
    verified_facts: list[str],
    assessment: str,
    recommendation: str,
    confidence: Literal["low", "medium", "high"],
    uncertainties: list[str],
    cited_finding_ids: list[str],
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Store the final decision brief; refused until the Critic has reviewed the findings.

    Args:
        headline: One-sentence conclusion.
        verified_facts: Facts only, each ending with its finding ID, e.g. "... [F1]".
        assessment: Interpretation, clearly separate from the facts.
        recommendation: The proposed action; it needs human approval before execution.
        confidence: Overall confidence.
        uncertainties: Open questions and caveats.
        cited_finding_ids: Every finding ID the brief relies on.
    """
    critique = tool_context.state.get(CRITIQUE_KEY)
    if not critique:
        return {"status": "error", "message": "The Critic has not reviewed the findings yet."}
    if critique["verdict"] == "needs_more_evidence":
        return {
            "status": "error",
            "message": "Critic requires more evidence.",
            "requested_follow_ups": critique["requested_follow_ups"],
        }
    findings = tool_context.state.get(FINDINGS_KEY) or []
    known_ids = {finding["finding_id"] for finding in findings}
    unknown = [item for item in cited_finding_ids if item not in known_ids]
    if unknown or not cited_finding_ids:
        return {"status": "error", "message": f"Unknown or missing finding IDs: {unknown}"}

    evidence_ids = sorted(
        {
            evidence_id
            for finding in findings
            if finding["finding_id"] in cited_finding_ids
            for evidence_id in finding["evidence_ids"]
        },
        key=lambda value: int(value[1:]),
    )
    tool_context.state[BRIEF_KEY] = {
        "headline": headline,
        "verified_facts": verified_facts,
        "assessment": assessment,
        "recommendation": recommendation,
        "requires_human_approval": True,
        "confidence": confidence,
        "uncertainties": uncertainties + critique["issues"],
        "finding_ids": cited_finding_ids,
        "evidence_ids": evidence_ids,
    }
    return {"status": "success", "evidence_ids": evidence_ids}

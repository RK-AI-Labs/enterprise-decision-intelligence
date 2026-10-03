from types import SimpleNamespace
from typing import Any

from ai_template_python.evidence import register_evidence
from ai_template_python.tools.analytics import investigation_state as tools


def _context() -> Any:
    return SimpleNamespace(state={})


def _evidence(context: Any, locator: str = "t:1", synthetic: bool = True) -> str:
    return register_evidence(
        context.state,
        source_type="database",
        source_id="S102",
        locator=locator,
        citation_label="label",
        excerpt=f"excerpt {locator}",
        is_synthetic=synthetic,
    )


def test_evidence_ids_are_stable_and_deduplicated() -> None:
    context = _context()
    assert _evidence(context, "a") == "E1"
    assert _evidence(context, "b") == "E2"
    assert _evidence(context, "a") == "E1"
    assert len(context.state["evidence"]) == 2


def test_findings_must_cite_registered_evidence() -> None:
    context = _context()
    evidence_id = _evidence(context)

    unknown = tools.record_finding("data_analyst", "x", "fact", ["E9"], "high", [], context)
    uncited_fact = tools.record_finding("data_analyst", "x", "fact", [], "high", [], context)
    ok = tools.record_finding("data_analyst", "x", "fact", [evidence_id], "high", ["syn"], context)

    assert unknown["status"] == "error"
    assert uncited_fact["status"] == "error"
    assert ok == {"status": "success", "finding_id": "F1"}


def test_critic_checks_flag_missing_caveats_and_coverage() -> None:
    context = _context()
    evidence_id = _evidence(context)
    tools.record_finding("data_analyst", "x", "fact", [evidence_id], "high", [], context)

    issues = tools.check_findings(context)["automated_issues"]

    assert any("synthetic" in issue for issue in issues)
    assert any("knowledge_agent" in issue for issue in issues)
    assert any("research_agent" in issue for issue in issues)


def test_brief_requires_critic_approval_and_valid_findings() -> None:
    context = _context()
    evidence_id = _evidence(context)
    tools.record_finding("data_analyst", "x", "fact", [evidence_id], "high", ["syn"], context)
    args = ("h", ["x [F1]"], "a", "r", "medium", [], ["F1"], context)

    assert tools.submit_decision_brief(*args)["status"] == "error"

    tools.record_critique("needs_more_evidence", ["gap"], ["get more"], context)
    assert tools.submit_decision_brief(*args)["message"] == "Critic requires more evidence."

    tools.record_critique("approved_with_caveats", ["synthetic"], [], context)
    bad = tools.submit_decision_brief("h", [], "a", "r", "low", [], ["F9"], context)
    result = tools.submit_decision_brief(*args)

    assert bad["status"] == "error"
    assert result == {"status": "success", "evidence_ids": ["E1"]}
    assert context.state["decision_brief"]["requires_human_approval"] is True
    assert context.state["decision_brief"]["uncertainties"] == ["synthetic"]


def test_decision_system_topology() -> None:
    from ai_template_python.agents.decision_system import create_decision_system

    root = create_decision_system("test-model")

    assert [agent.name for agent in root.sub_agents] == [
        "data_analyst",
        "knowledge_agent",
        "research_agent",
        "critic_agent",
        "decision_agent",
    ]

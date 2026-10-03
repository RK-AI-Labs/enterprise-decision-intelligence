"""Evidence registry stored in shared ADK session state.

Tools register every source they read and return the evidence ID. Findings may only cite
registered IDs, which keeps conclusions traceable to a database row set, document chunk,
or external series.
"""

import hashlib
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from ai_template_python.state import EvidencePointer

EVIDENCE_KEY = "evidence"
FINDINGS_KEY = "findings"
CRITIQUE_KEY = "critique"
BRIEF_KEY = "decision_brief"


def register_evidence(
    state: MutableMapping[str, Any],
    *,
    source_type: str,
    source_id: str,
    locator: str,
    citation_label: str,
    excerpt: str,
    is_synthetic: bool,
) -> str:
    """Add (or reuse) an evidence record and return its stable ID such as ``E1``."""
    content_sha256 = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    records: list[EvidencePointer] = list(state.get(EVIDENCE_KEY) or [])
    for record in records:
        if record["locator"] == locator and record["content_sha256"] == content_sha256:
            return record["evidence_id"]

    evidence_id = f"E{len(records) + 1}"
    records.append(
        {
            "evidence_id": evidence_id,
            "source_type": source_type,  # type: ignore[typeddict-item]
            "source_id": source_id,
            "locator": locator,
            "observed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "content_sha256": content_sha256,
            "citation_label": citation_label,
            "excerpt": excerpt[:600],
            "is_synthetic": is_synthetic,
        }
    )
    state[EVIDENCE_KEY] = records
    return evidence_id

# ADR-0003: Require Human Approval for Consequential Actions

- Status: Accepted
- Date: 2026-10-03

## Context

Procurement analysis can influence material financial decisions. An LLM-generated recommendation is not authorization to modify a purchase order, contact a supplier, approve/reject a transaction, or disclose tenant data. Investigation should remain useful without silently taking such actions.

## Decision

The initial system is read-only. Human approval is required before any future consequential write or external disclosure. Human review is also required when the Critic cannot resolve material evidence conflicts, required evidence is missing, claims remain unsupported, confidence is insufficient, or configured policy/materiality thresholds require an approver.

Approval requests are explicit, scoped to an exact action and reviewed version, and include reason and evidence references. Decisions persist actor, timestamp, outcome, and rationale. The model cannot approve its own action. Rejection or timeout results in no action.

## Consequences

- A future write-capable integration must use a separate authorized action boundary, not broaden read-only investigation tools.
- The workflow needs an `awaiting_human` state and resumable events.
- UI approval is a request to the API, not a security boundary.
- Human review does not convert unsupported claims into facts; evidence and uncertainty remain visible.

## Alternatives Considered

- Allow the Decision agent to execute recommended actions: rejected because model output is not sufficient authorization for financial or external side effects.
- Require approval for every read-only lookup: rejected because it adds friction without proportionate risk; tool allowlists, tenant policies, and budgets constrain investigation access.
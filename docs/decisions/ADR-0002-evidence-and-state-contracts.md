# ADR-0002: Use Versioned State and Evidence References

- Status: Accepted
- Date: 2026-10-03

## Context

An investigation combines SQL results, internal documents, and external data. Durable conclusions must be auditable and parallel agents must not overwrite one another's state. ADK session state is useful working memory but is not an appropriate system of record.

## Decision

Use a versioned, JSON-serializable investigation state contract. Persist investigation lifecycle, findings, evidence metadata/references, events, and approval records in application-owned storage. Store large source payloads in their controlled data stores and pass references rather than copying complete payloads into shared agent state.

The initial document-search contract does not imply that reference documents or a corpus are already present. Contracts, policies, and supplier documents will be onboarded in a later milestone. Until then, document-backed investigation must report the source as not configured rather than inventing evidence; a successful no-match result is reserved for a configured corpus and includes its version.

Specialists return typed results/events; the orchestrator or investigation service applies validated state transitions. Evidence-bearing findings reference stable evidence IDs and preserve source, locator, observed/retrieved time, and content version/hash when available. Tool contracts remain independent from ADK and infrastructure implementations.

## Consequences

- State migrations and schema-version validation are required as the workflow evolves.
- Evidence metadata must be persisted before dependent findings are marked complete.
- Parallel specialists cannot directly mutate canonical workflow state.
- Tool adapters can be unit-tested independently from ADK, PostgreSQL, Qdrant, and external APIs.
- The current Python package is still named `ai_template_python`; moving these contracts during the planned package rename is a follow-up, not a reason to couple them to the frontend.

## Alternatives Considered

- Keep all state only in ADK session storage: simpler initially, but insufficient for durable audit, reconnectable event streams, and long-lived investigations.
- Put full tool results/documents in shared state: convenient for agents, but increases token cost, race risk, privacy exposure, and state size.
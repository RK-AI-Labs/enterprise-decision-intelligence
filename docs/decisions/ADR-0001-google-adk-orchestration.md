# ADR-0001: Use Google ADK for Agent Orchestration

- Status: Accepted
- Date: 2026-10-03

## Context

The project must demonstrate meaningful specialist delegation, bounded multi-agent investigation, and observable tool use. A framework-independent domain/tool layer is also required so business rules remain testable and the project is not coupled to a single agent SDK.

## Decision

Use Google Agent Development Kit (ADK) as the runtime and orchestration layer. The Orchestrator is the root agent and coordinates the Data Analyst, Knowledge, Research, Critic, and Decision agents. Specialist tools are exposed through thin ADK adapters over framework-independent typed contracts. FastAPI owns authentication, request lifecycle, persistence, streaming, and authorization; it does not delegate those responsibilities to the model.

The initial workflow permits parallel read-only specialist work, requires Critic validation before Decision synthesis, and allows at most one bounded follow-up round.

## Consequences

- ADK-specific code is isolated under the future `agents/` integration layer.
- Core contracts and deterministic services can be tested without model calls or ADK.
- Agent execution and tool results require explicit budgets, deadlines, and observability.
- ADK is an architectural dependency; replacing it later would require adapting orchestration and session integration, but not the domain contracts.

## Alternatives Considered

- LangGraph: capable orchestration, but overlaps with the existing `enterprise-rag` portfolio project and does not meet this project's Google ADK objective.
- Direct model/API calls in FastAPI: fewer dependencies, but does not provide the intended explicit agent delegation/runtime boundary.
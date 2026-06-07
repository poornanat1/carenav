# CareNav — Documentation

Structured development docs derived from the build spec ([internal/spec.md](../internal/spec.md)).
Each doc is scoped to a subsystem so it can guide implementation independently.

## Reading order

| # | Doc | Covers |
|---|---|---|
| 00 | [Overview](00-overview.md) | Vision, scope, safety boundary, role mapping |
| 01 | [Architecture](01-architecture.md) | System diagram, hot/cold path, repo layout |
| 02 | [Tech Stack & Decisions](02-tech-stack.md) | Stack choices + settled open decisions |
| 03 | [Orchestrator](03-orchestrator.md) | Typed node pipeline (§4.1) |
| 04 | [Specialist Agents](04-agents.md) | Tool agents + contracts (§4.2) |
| 05 | [PII/PHI Redaction](05-redaction.md) | The security spine (§4.3) |
| 06 | [Model Tiering & Escalation](06-model-tiering.md) | Tiers, confidence, escalation (§4.4) |
| 07 | [RAG Subsystem](07-rag.md) | Corpus, chunking, grounding (§4.5) |
| 08 | [Data Model & Pipeline](08-data-model.md) | Entities + ingestion (§5) |
| 09 | [Eval Framework](09-eval.md) | CUJs, metrics, CI gates (§6) |
| 11 | [Observability & Cost](11-observability.md) | Tracing + cost accounting (§8) |
| 12 | [Scalability & Deployment](12-scalability.md) | Scale-out story (§9) |
| 13 | [Build Plan](13-build-plan.md) | Milestones M0–M6 (§11) |
| 14 | [Deployment Mapping](14-deployment-mapping.md) | Cloud-agnostic deployment mapping (§13) |
| 15 | [Risks & Non-Goals](15-risks-non-goals.md) | Posture, hard boundaries (§12) |

## Two rules that override everything

1. **Missed-escalation rate must be 0.** An emergent or high-stakes turn that is not escalated to a human blocks merge — regardless of any other metric. See [09-eval.md](09-eval.md).
2. **PII-leakage rate must be 0.** No unredacted PHI ever reaches a model input. See [05-redaction.md](05-redaction.md).

These are the two **hard gates**. Everything else is a tunable soft threshold.

## Settled decisions (from §14 of the spec)

- **Models:** Mistral (`mistral-small-latest` = small tier, `mistral-large-latest` = frontier tier).
- **Database / vector store:** managed Postgres + pgvector.
- **Frontend:** React.

See [02-tech-stack.md](02-tech-stack.md) for details and implications.

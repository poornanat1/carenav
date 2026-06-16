# 14 — Deployment Mapping

Implements spec §13. The core stays **cloud-agnostic by design**; this doc maps each
CareNav component onto a generic managed-service category so it can land on any cloud.

## Component → managed-service category

| CareNav component | Managed-service category |
|---|---|
| Orchestrator (typed Python pipeline) | Container service / serverless runtime |
| Tier 1 / Tier 2 models | Managed model-serving endpoint or provider API (**Fireworks** by default) |
| Model gateway / serving | Container service fronting the model API/endpoint |
| RAG vector store | Managed **Postgres + pgvector**, or a managed vector-search service |
| PII/PHI redaction | Managed sensitive-data / DLP service (analog to Presidio) |
| Synthea structured/FHIR data | A FHIR store (Synthea exports FHIR — clean on-ramp) |
| Async queue | Managed queue |
| Conversation state | Managed key-value / cache store |
| Eval | CI + an eval service |
| The CX framing | A conversational-support / contact-center product line |
| Value dashboard | A BI / dashboarding tool |
| Tracing / cost | Managed tracing + monitoring |

## The one-liner

*The architecture is cloud-agnostic by design; every component has a first-class
managed-service equivalent, and Synthea's FHIR output drops straight into any FHIR
store.*

## How the settled decisions land

The settled choices ([02](02-tech-stack.md)) make several of these mappings the
**actual implementation**, not just analogs:

- **Models** → Fireworks via API (`mistral-small-24b-instruct-2501` /
  `mistral-large-3-fp8`), reached through
  the provider-agnostic `ModelGateway`.
- **PII detector** → Fireworks supervised fine-tune, deployed as a LoRA route on a
  base-model deployment.
- **Embeddings** → Mistral `mistral-embed`, called through the same gateway.
- **DB + vector store** → managed Postgres + pgvector (the real store), with a
  backend-neutral retrieval interface.

The provider-agnostic `ModelGateway` and backend-neutral retrieval interface preserve
the "cloud-agnostic core" claim regardless of where it is deployed.

## Where this doc lives

This file (`docs/14-deployment-mapping.md`) is its home in the numbered doc set; if a
separate `docs/deployment-mapping.md` is desired for README linking, keep the two in
sync or symlink.

# 02 — Tech Stack & Settled Decisions

## Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | **Python 3.11+** | The whole repo |
| Orchestration | **Typed Python pipeline** | Hand-written node-functions; linear flow + bounded retry, each node unit-testable, see [03](03-orchestrator.md) |
| Serving | **FastAPI + Uvicorn** | Async turn endpoint |
| Schemas / validation | **Pydantic v2** | All tool I/O and graph state typed |
| Model access | Thin **`ModelGateway`** abstraction | Provider-swappable; per-call tier + cost capture |
| Embeddings + vector store | **pgvector** on Postgres | Hybrid vector + full-text retrieval in one SQL function (`hybrid_search`) |
| PII detection | **Presidio + spaCy NER** + deterministic field-based redaction | Detects and redacts PHI before any model input |
| Structured data | **Postgres-only** (managed in prod) | Members/claims/conditions/providers/benefit rules; one database everywhere |
| Eval | **pytest** + custom `eval/` harness; LLM-as-judge for rubric scoring | CI-gateable |
| Frontend | **React** | Chat view |
| Observability | **OpenTelemetry** traces + structured JSON logs | Per-turn span tree |
| Packaging | **Docker**, `uv` / `pip-tools` | One `docker compose up` to run end-to-end |

## Settled open decisions (§14 of spec)

These were left open in the spec and are now decided:

| Decision | Choice | Implication |
|---|---|---|
| **Model providers** | **Mistral** — `mistral-small-latest` (small/Tier 1), `mistral-large-latest` (frontier/Tier 2) | The GEPA-style quality-vs-cost chart and all cost numbers are computed against this pair. The `ModelGateway` stays provider-agnostic so the pair can be swapped. |
| **Vector store** | **pgvector on Postgres** | One fewer moving part, prod-shaped. Retrieval is a single `hybrid_search` SQL function (vector + full-text). |
| **Frontend** | **React** | Reads more "product" than Streamlit; costs more frontend time. |
| **Structured DB** | **Postgres** | Same engine as the vector store. **Postgres everywhere** — pgvector + full-text are core to retrieval, dev, and prod. |
| **Benefit-rule data** | **Minimal & documented** | The single hand-built artifact; keep it small, plausible, and explained inline. |

## Design implications of the Mistral choice

- Tier 1 / Tier 2 map cleanly to **`mistral-small-latest` / `mistral-large-latest`**.
- pgvector lives in **Postgres** — the same Postgres instance can hold both
  structured tables and embeddings, simplifying the deployment story.
- The `ModelGateway` must still expose a provider-agnostic interface (other providers
  swappable) so the "model integration" grading point holds — Mistral is the
  *default*, not a hard dependency. See [06-model-tiering.md](06-model-tiering.md).

## Provider-agnostic boundary (non-negotiable)

Even though Mistral is the chosen provider, **no application code outside
`carenav/models/` may import a provider SDK directly.** Everything goes through
`ModelGateway`. This keeps cost capture centralized and the swap story credible.

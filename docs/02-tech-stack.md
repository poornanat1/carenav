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
| PII detection | Deterministic field matching + regex + **Fireworks fine-tuned LoRA** | Detects and redacts PHI before any model input; falls back safely when the model layer is unavailable |
| Structured data | **Postgres-only** (managed in prod) | Members/claims/conditions/providers/benefit rules; one database everywhere |
| Eval | **pytest** + custom `eval/` harness; LLM-as-judge for rubric scoring | CI-gateable |
| Frontend | **React** | Chat view |
| Observability | **OpenTelemetry** traces + structured JSON logs | Per-turn span tree |
| Packaging | **Docker**, `uv` / `pip-tools` | One `docker compose up` to run end-to-end |

## Settled open decisions (§14 of spec)

These were left open in the spec and are now decided:

| Decision | Choice | Implication |
|---|---|---|
| **Model providers** | **Fireworks** — `accounts/fireworks/models/gpt-oss-20b` (small/Tier 1), `accounts/fireworks/models/gpt-oss-120b` (frontier/Tier 2); **Mistral** — `mistral-embed` for embeddings | The gateway stays provider-agnostic while using Fireworks for generation and managed PII fine-tuning. Embeddings remain Mistral-backed at 1024 dimensions. |
| **Vector store** | **pgvector on Postgres** | One fewer moving part, prod-shaped. Retrieval is a single `hybrid_search` SQL function (vector + full-text). |
| **Frontend** | **React** | Reads more "product" than Streamlit; costs more frontend time. |
| **Structured DB** | **Postgres** | Same engine as the vector store. **Postgres everywhere** — pgvector + full-text are core to retrieval, dev, and prod. |
| **Benefit-rule data** | **Minimal & documented** | The single hand-built artifact; keep it small, plausible, and explained inline. |

## Design implications of the provider split

- Tier 1 / Tier 2 map to Fireworks-hosted **`gpt-oss-20b` / `gpt-oss-120b`**.
- The PII detector is trained as a Fireworks supervised fine-tune, then deployed as a
  LoRA route in the form `<fine_tuned_model>#<deployment>`.
- Retrieval embeddings continue to use **`mistral-embed`**; keep `EMBEDDING_DIM=1024`
  aligned with the pgvector column.
- pgvector lives in **Postgres** — the same Postgres instance can hold both
  structured tables and embeddings, simplifying the deployment story.
- The `ModelGateway` must still expose a provider-agnostic interface (other providers
  swappable) so the "model integration" grading point holds. See
  [06-model-tiering.md](06-model-tiering.md).

## Provider-agnostic boundary (non-negotiable)

No application code outside `carenav/models/` may import a provider SDK directly.
Everything goes through `ModelGateway`. This keeps cost capture centralized and the
swap story credible.

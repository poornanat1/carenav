# CareNav — Orchestrated Health-Benefits & Care Navigator

A production-grade, tool-using conversational assistant that helps health-plan
members with coverage, benefits, claims, provider search, and medication info — with a
PII-redaction security layer, tiered-model cost optimization, and an eval-driven quality
bar.

> **Not a diagnostic or medical-advice tool.** It navigates benefits and surfaces
> vetted info; clinical judgment escalates to humans. **All patient/member PHI is
> synthetic** (Synthea) — never wired to real PHI. Provider data is real but public
> (NPPES), and contains no patient information.

The [docs/](docs/) describe the **full target system**; the code is being built up to it
in stages. Below: what runs today, then what's on the roadmap. (An empty package
directory is a placeholder for a roadmap item.)

## What works today

| Capability | What it does | Where |
|---|---|---|
| **Data pipeline** | One command builds the demo dataset — real Synthea members/claims/conditions, real public providers (NPPES), a benefit-rule table, and a knowledge-base corpus embedded into Postgres/pgvector. | `src/carenav/data`, `src/carenav/rag/ingest_kb.py` |
| **Grounded Q&A** | Ask a benefits/medication question → a cited, fact-checked answer. Every sentence must cite a source chunk; unsupported claims are stripped or the answer escalates instead of guessing. | `src/carenav/rag` |
| **Hybrid retrieval** | One Postgres function (`hybrid_search`): pgvector ANN + weighted full-text + a doc-level relevance prune, so named entities (a specific drug, the Silver plan) anchor correctly. | `src/carenav/rag/sql` |
| **Orchestrator + tools** | A typed node pipeline routes a turn (safety triage → intent → decompose → run specialist tools → grounded answer → verify → escalate). Tools (member, coverage, claims, provider) return structured data and their facts are cited & grounded like KB chunks. | `src/carenav/{orchestrator,agents}` |
| **Tiered routing + escalation** | Composite confidence picks a cheap model when confident, a stronger one when not, a human when neither is safe. Emergent turns escalate immediately. | `src/carenav/orchestrator` |
| **FastAPI endpoint** | `POST /turn` runs a member turn and returns the structured answer or escalation handoff. | `src/carenav/api` |
| **Model gateway** | The one place any AI provider is called. Captures token cost per call, retries on rate limits, and can run a no-cost offline stub. | `src/carenav/models` |

## Roadmap

| Capability | What it will add | Where |
|---|---|---|
| **PII redaction** | Replace patient info with tokens before anything reaches a model; rehydrate only the final reply. | `src/carenav/redaction` |
| **Eval + CI gates** | A golden test set that fails the build if safety or grounding regresses. | `eval/` |
| **Observability** | OpenTelemetry per-turn span tree + structured logs. | `src/carenav/telemetry` |
| **Frontend** | React chat view over the `/turn` endpoint. | `frontend/` |

The order these are being built (and why) is in [docs/13-build-plan.md](docs/13-build-plan.md).

## See it work (60 seconds)

```bash
cp .env.example .env            # add FIREWORKS_API_KEY for generation; MISTRAL_API_KEY for embeddings
make db-up && make install      # Postgres (pgvector) + deps
make data                       # build the dataset + embed the KB corpus

# ask a grounded, cited question through the orchestrator:
python -c "from carenav.orchestrator import run_turn as t; \
r=t('What are the side effects of metformin?'); \
print(r.answer); print([c.chunk_id for c in r.citations])"
```

A multi-tool turn fuses the member's record with plan rules — e.g. *"Have I met my
deductible, and is an MRI covered on my plan?"* runs the **member-account** and
**benefit** tools and grounds the answer over both:
*"You have met your $4,000 deductible … An MRI is covered with 40% coinsurance after the
deductible and requires prior authorization."* (Pass a `member_ref` from
`carenav.agents.create_member_ref(member_id)`.)

### Run it in Docker instead

```bash
docker compose up -d            # db + app container
docker compose exec app make data
```

`make` targets: `make help` lists them. Key ones — `make data` (build dataset),
`make test` (suite), `make run` (FastAPI `/turn` endpoint), `make eval` (safety/grounding
gates, once built). Python 3.11+ is required; use the container if older.

## Architecture

The turn flow. Steps in **bold** run today; `redact` is the remaining planned node.

```
user turn → Orchestrator (typed node pipeline):
  **safety_triage → route → decompose →**
  **[plan → tool_exec → reflect] → generate →**
  **groundedness_check → verify →** redact → respond / escalate
```

The orchestrator is a **hand-written, typed Python pipeline** — one pure function per node
in [run_turn()](src/carenav/orchestrator/turn.py), composed in sequence with one bounded
frontier retry. Each node is independently unit-testable. Everything runs over the **model
gateway** ([gateway.py](src/carenav/models/gateway.py)), which captures token cost per call.

- **Specialist agents (tools):** Member/Account, Coverage/Benefit, Claims, Provider
  search — typed Pydantic in/out, structured data, **never call a model**. Their facts are
  wrapped as groundable sources and cited `[CHUNK:tool:<name>]` like KB chunks. The Triage
  classifier lives in the `route` node. *(all built; tool-output redaction is built.)*
- **Cross-cutting layers:** model gateway with cost capture, hybrid RAG retrieval,
  confidence tiering with frontier retry + human handoff *(built)*; PII redaction,
  telemetry, eval harness *(planned)*.
- **Data:** Synthea (members/claims/conditions/FHIR) · NPPES (providers) · benefit-rule
  table · KB corpus (vector store). *(all built.)*

See [docs/01-architecture.md](docs/01-architecture.md) and
[docs/03-orchestrator.md](docs/03-orchestrator.md).

## The two hard gates

1. **Missed-escalation rate = 0** — emergent/high-stakes turns must escalate to a human.
2. **PII-leakage rate = 0** — no unredacted PHI ever reaches a model input.

Both are CI-enforced ([docs/09-eval.md](docs/09-eval.md)).

## Tech stack

Python 3.11+ · typed orchestrator pipeline · FastAPI · Pydantic v2 · Postgres + pgvector
(hybrid vector + full-text) · three-layer PHI redaction · Fireworks
(`gpt-oss-20b`/`gpt-oss-120b`) for generation and PII fine-tuning · Mistral
(`mistral-embed`) for embeddings · React frontend · OpenTelemetry. See
[docs/02-tech-stack.md](docs/02-tech-stack.md).

## Repo layout

`✅` = built, `⬜` = scaffold/placeholder for a planned capability.

```
src/carenav/
  data/         ✅ ingest + database models (Synthea, NPPES, benefits, KB)
  rag/          ✅ chunking, embeddings, hybrid retrieval (sql/), grounded Q&A agent
  models/       ✅ model gateway (the only place a provider SDK is imported)
  orchestrator/ ✅ typed node pipeline (route, decompose, tool loop, verify, escalate)
  agents/       ✅ specialist tools (member, benefits, claims, provider)
  api/          ✅ FastAPI turn endpoint
  redaction/    ✅ PII detection, tokenization, Fireworks SFT training
  telemetry/    ⬜ tracing + structured logs
eval/           ⬜ golden test set · metrics · run.py
frontend/       ⬜ React chat (not yet created)
docs/           design docs for the full target system (see below)
tests/          pytest suite for the built modules
```

## Docs — where to start

The [docs/](docs/) folder is the full design (the *target* — not all of it is built
yet). If you only read three: **[00-overview](docs/00-overview.md)** (what & why) →
**[01-architecture](docs/01-architecture.md)** (the turn flow) →
**[13-build-plan](docs/13-build-plan.md)** (what's built and what's next). For a specific
subsystem, jump to its numbered doc (e.g. [07-rag](docs/07-rag.md),
[05-redaction](docs/05-redaction.md), [09-eval](docs/09-eval.md)).

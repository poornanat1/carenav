# CareNav

A conversational assistant that helps health-plan members with coverage, benefits,
claims, provider search, and medication questions. Every answer is grounded in a cited
source — and when a question is unsafe or unanswerable, it escalates to a human instead
of guessing.

### 🚀 [Try the live demo](https://carenav-frontend-production.up.railway.app)

Pick a member, then ask about their coverage, claims, or care. All member data is
synthetic.

> **Not medical advice.** CareNav navigates benefits and surfaces vetted information;
> clinical judgment goes to humans. All member/patient data is synthetic
> ([Synthea](https://synthetichealth.github.io/synthea/)) — never real PHI. Provider data
> is real but public (NPPES) and contains no patient information.

---

## What it does

| | |
|---|---|
| **Grounded answers** | Every factual sentence must cite a retrieved source. Unsupported claims are stripped; if nothing supports the answer, the turn escalates rather than guess. |
| **Tool-using orchestrator** | A typed pipeline routes each turn: safety check → intent → run specialist tools (member, benefits, claims, providers) → grounded answer → verify → respond or escalate. |
| **Hybrid retrieval** | One Postgres function combines pgvector similarity, full-text ranking, and a doc-level relevance prune, so a specific drug or plan name anchors the right source. |
| **Cost-aware model tiering** | A cheap model handles confident turns, a stronger one handles hard ones, and a human handles the rest. Emergencies escalate immediately. |
| **PII redaction** | User text and tool outputs are tokenized before any model call and rehydrated only in the final response. |
| **Multi-turn context** | A follow-up like "what are the side effects?" is resolved against the prior turns before routing. |

Built on a typed Python orchestrator, FastAPI, Postgres + pgvector, Mistral models, and a
React frontend. The [docs/](docs/) describe the full target design; **telemetry** is the
remaining roadmap item. The eval gates are live: `make eval` runs the golden CUJ suite
and fails CI on a missed escalation or a PII leak ([docs/09-eval.md](docs/09-eval.md)).

## Quick start

The fastest path is the [live demo](https://carenav-frontend-production.up.railway.app) —
no setup. To run it locally:

```bash
cp .env.example .env          # add MISTRAL_API_KEY (generation + embeddings)
make db-up && make install    # Postgres (pgvector) + dependencies
make data                     # build the demo dataset + embedded knowledge base
```

Ask a grounded question from the shell:

```bash
python -c "from carenav.orchestrator import run_turn; \
r = run_turn('What are the side effects of metformin?'); \
print(r.answer, [c.chunk_id for c in r.citations])"
```

Or run the full app:

```bash
make run                      # API on http://localhost:8000
make frontend-install         # once
make frontend                 # UI on http://localhost:5173
```

Prefer containers? `docker compose up -d` then `docker compose exec app make data`.
Python 3.11+ is required; use the container if your local Python is older. Run
`make help` for all targets.

### A turn in action

The question *"Have I met my deductible, and is an MRI covered on my plan?"* runs two
tools — the member account and the benefit lookup — and grounds a single answer over
both:

> You've met your $4,000 deductible. An MRI is covered at 40% coinsurance after the
> deductible and requires prior authorization.

(Pass a `member_ref` from `carenav.agents.create_demo_member_ref(member_id)`.)

## How it works

```
turn → API member gate → orchestrator:
       query analysis → redact → safety check → route → decompose →
       [plan → run tools → reflect] → generate →
       groundedness check → verify → respond or escalate
```

The orchestrator is a hand-written, typed pipeline — one pure function per step in
[run_turn()](src/carenav/orchestrator/turn.py), with one bounded retry on a stronger
model. Every step is unit-testable, and every model call goes through the
[gateway](src/carenav/models/gateway.py) that records token cost.

- **Specialist tools** (member, benefits, claims, providers) take and return typed
  Pydantic data and never call a model. Their facts are wrapped as citeable sources and
  grounded just like knowledge-base chunks.
- **Profile routing** keeps selected-member questions on member facts and general health
  questions on the public knowledge base — even when a member is selected.
- **Data**: Synthea (members, claims, conditions) · NPPES (real public providers) · a
  benefit-rule table · a generated condition index · the embedded KB corpus.

More detail in [docs/01-architecture.md](docs/01-architecture.md) and
[docs/03-orchestrator.md](docs/03-orchestrator.md).

## Two hard guarantees

1. **No missed escalations** — emergent or high-stakes turns always reach a human.
2. **No PII leakage** — unredacted PHI never reaches a model input.

Both are enforced in CI ([docs/09-eval.md](docs/09-eval.md)).

## Repo layout

```
src/carenav/
  data/          ingest + database models (Synthea, NPPES, benefits, KB)
  rag/           chunking, embeddings, hybrid retrieval, grounded Q&A
  models/        the model gateway — the only place a provider SDK is imported
  orchestrator/  the typed turn pipeline (route, tools, verify, escalate)
  agents/        specialist tools (member, benefits, claims, providers)
  api/           FastAPI app, member summaries, profile routing
  redaction/     PII detection, tokenization, fine-tune training
  telemetry/     tracing + structured logs (roadmap)
eval/            golden CUJ suite + metrics + hard gates (`make eval`)
frontend/        React chat UI
docs/            full design docs
tests/           pytest suite
```

## Docs

The [docs/](docs/) folder is the full design — the target, not all of it shipped yet. If
you read three, read them in this order:

1. [00-overview](docs/00-overview.md) — what and why
2. [01-architecture](docs/01-architecture.md) — the turn flow
3. [13-build-plan](docs/13-build-plan.md) — what's built and what's next

For a subsystem, jump to its numbered doc — e.g. [07-rag](docs/07-rag.md),
[05-redaction](docs/05-redaction.md), [09-eval](docs/09-eval.md). Deployment lives in
[docs/DEPLOY.md](docs/DEPLOY.md).

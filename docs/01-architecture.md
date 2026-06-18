# 01 — Architecture

## System overview

```
                          ┌─────────────────────────────────────┐
   user turn  ──────────► │  Orchestrator (typed node pipeline)  │
                          │                                      │
                          │  ingest → safety_triage → redact →   │
                          │  route → [plan ⇄ tool_exec ⇄ reflect]│
                          │  → generate → groundedness_check →   │
                          │  rehydrate → respond / escalate      │
                          └───────┬───────────────┬──────────────┘
                                  │               │
              ┌───────────────────┘               └───────────────────┐
              ▼                                                        ▼
   ┌────────────────────┐                                  ┌────────────────────┐
   │ Specialist agents  │                                  │  Cross-cutting      │
   │ (tools)            │                                  │  layers             │
   │ • Member/Account   │                                  │ • PII redaction     │
   │ • Coverage/Benefit │                                  │ • Model gateway     │
   │ • Claims           │                                  │   (tiered)          │
   │ • Provider search  │                                  │ • Retrieval (RAG)   │
   │ • KB/RAG           │                                  │ • Telemetry/cost    │
   │ • Triage classifier│                                  │ • Eval harness      │
   └─────────┬──────────┘                                  └────────────────────┘
             ▼
   ┌────────────────────────────────────────────────────────┐
   │ Data: Synthea (members/claims/FHIR) · NPPES (providers) │
   │       · Benefit rules table · KB corpus (vector store)  │
   └────────────────────────────────────────────────────────┘
```

## Hot path vs cold path

**Hot path** (turn serving) and **cold path** (eval, telemetry, batch ingest) are
strictly separated so the cold path never blocks a response.

- **Hot path:** the orchestrator graph + specialist tools + model gateway + RAG retrieval.
- **Cold path:** data ingestion, eval runs, telemetry export, batch re-embedding.

Anything off the hot path goes through an async queue (see [12-scalability.md](12-scalability.md)).

## Layered responsibilities

| Layer | Owns | Detail |
|---|---|---|
| Orchestrator | Control flow, ReAct loop, generation, escalation | [03](03-orchestrator.md) |
| Specialist agents | Typed data lookups (no model calls) | [04](04-agents.md) |
| Redaction | Tokenize PHI before any model sees it | [05](05-redaction.md) |
| Model gateway | Provider-agnostic calls, tiering, cost capture | [06](06-model-tiering.md) |
| RAG | Chunk, embed, retrieve, ground | [07](07-rag.md) |
| Data | Ingest Synthea/NPPES/KB into stores | [08](08-data-model.md) |
| Telemetry | Spans, cost accounting, structured logs | [11](11-observability.md) |
| Eval | CUJ harness, metrics, CI gates | [09](09-eval.md) |
| API | FastAPI async turn endpoint | this doc |

## Repo structure

```
carenav/
├── README.md                      # what, why, and how to run
├── docs/                          # these documents
├── carenav/
│   ├── orchestrator/              # typed node pipeline: route/plan/tool_exec/reflect (§4.1)
│   ├── agents/                    # specialist tools (§4.2)
│   ├── redaction/                 # PII/PHI layer (§4.3)
│   ├── models/                    # ModelGateway, tiering, confidence (§4.4)
│   ├── rag/                       # chunking, embeddings, retrieval, grounding (§4.5)
│   ├── data/                      # ingest scripts: synthea, nppes, kb, benefits (§5)
│   ├── telemetry/                 # tracing + cost accounting (§8)
│   └── api/                       # FastAPI serving
├── eval/
│   ├── cujs/                      # golden fixtures (§6.1)
│   ├── metrics/                   # metric implementations (§6.2)
│   └── run.py                     # harness + report (§6.3)
├── frontend/                      # React chat view
├── tests/
├── docker-compose.yml
└── Makefile                       # `make data`, `make eval`, `make run`
```

## Key architectural invariants

1. PHI lives **only** in the out-of-band `pii_map`, never in `messages`/`tool_results`/logs.
2. Specialist agents return **structured data, not prose**, and never call a model.
3. Every agent result passes **through redaction** before re-entering graph state.
4. Retrieved KB text is treated as **data, never as instructions** (injection defense).
5. Every model call has a **timeout + fallback tier**; hard failure degrades to **human handoff**, never to a wrong answer.

# 12 — Scalability & Deployment

Implements spec §9. The "scale from internal pilot to external product" narrative —
state it explicitly in the README.

## Local

```
docker compose up
```

Runs FastAPI + Postgres + vector store + React frontend end-to-end.

## Architecture for scale (10k internal → millions external)

| Lever | Detail |
|---|---|
| **Stateless app services** | Behind a load balancer; conversation state in a fast external store (Redis / a managed key-value store), **never in-process**. |
| **Async queue** | A managed queue (SQS / Celery / etc.) for anything off the hot path: ingestion, eval logging, telemetry export, batch re-embedding. **Autoscale workers on queue depth.** |
| **Model gateway** | Centralizes rate-limiting, retries with backoff, and a **semantic cache** — at high volume, caching cuts both latency and model spend materially. |
| **Scale-out, not up** | Same stateless services replicated horizontally; add regional deployments + per-tenant isolation for the external (millions) tier. The **tiered-model design keeps unit cost flat as volume grows.** |
| **Failure posture** | Every model call has a timeout + fallback tier; a hard failure degrades to **human handoff, never to a wrong answer.** |

## Why the tiered design is the scaling story

Unit cost staying flat as volume grows is the whole pitch: most turns are served by the
small model (Tier 1), the frontier model (Tier 2) is reserved for low-confidence turns,
and the semantic cache absorbs repeat queries. See
[06-model-tiering.md](06-model-tiering.md).

## Hot/cold separation (recap)

The hot path (turn serving) and cold path (ingest, eval, telemetry, re-embedding) are
separated so the cold path never blocks a response
([01-architecture.md](01-architecture.md)). Everything cold goes through the queue.

### Pipeline orchestration — deliberately none (yet)

The data pipeline is a one-shot, idempotent, in-process build (`make data`) run on a
fresh clone or in CI — not a recurring, distributed, multi-worker DAG. A workflow
orchestrator (Airflow / Dagster / Prefect) would add a scheduler, a metadata DB, and a
daemon — operational surface that contradicts the "clone → `make data` → done"
reproducibility that is the project's selling point. The genuine orchestration need is
the **eval + CI gates**, already modeled correctly as a CI job. **When to revisit:** if
the KB corpus needs *periodic re-ingestion* from live MedlinePlus/openFDA or scheduled
NPPES monthly refreshes feeding a production index, reach for a lightweight asset
orchestrator (Dagster's local-dev + lineage story fits best) — or a managed
scheduler / workflow service ([14-deployment-mapping.md](14-deployment-mapping.md))
without standing up Airflow yourself.

## Deployment mapping

See [14-deployment-mapping.md](14-deployment-mapping.md): stateless service containers,
a managed queue, an external state store, and a model-serving endpoint.

## Build order

Scalability is documented as part of **M6** alongside the deployment mapping.
See [13-build-plan.md](13-build-plan.md).

# 12 — Scalability & Deployment

Implements spec §9. Covers how CareNav scales from an internal pilot to an external
product.

## Local

```
docker compose up
```

Runs FastAPI + Postgres + vector store + React frontend end-to-end.

## Architecture for scale (10k internal → millions external)

| Lever | Detail |
|---|---|
| **Stateless app services** | Behind a load balancer. Conversation state lives in a fast external store (Redis or a managed key-value store), never in-process. |
| **Async queue** | A managed queue (SQS, Celery, etc.) for anything off the hot path: ingestion, eval logging, telemetry export, batch re-embedding. Workers autoscale on queue depth. |
| **Model gateway** | Centralizes rate-limiting, retries with backoff, and a semantic cache. At high volume, caching cuts both latency and model spend materially. |
| **Scale-out, not up** | The same stateless services replicate horizontally. For the external (millions) tier, add regional deployments and per-tenant isolation. The tiered-model design keeps unit cost flat as volume grows. |
| **Failure posture** | Every model call has a timeout and a fallback tier. A hard failure degrades to human handoff, never to a wrong answer. |

## Why the tiered design keeps cost flat

Unit cost stays flat as volume grows. Most turns are served by the small model
(Tier 1). The frontier model (Tier 2) is reserved for low-confidence turns, and the
semantic cache absorbs repeat queries. See [06-model-tiering.md](06-model-tiering.md).

## Hot/cold separation (recap)

The hot path (turn serving) and cold path (ingest, eval, telemetry, re-embedding) are
separated so the cold path never blocks a response
([01-architecture.md](01-architecture.md)). Everything cold goes through the queue.

### Pipeline orchestration — deliberately none (yet)

The data pipeline is a one-shot, idempotent, in-process build (`make data`) run on a
fresh clone or in CI. It is not a recurring, distributed, multi-worker DAG. A workflow
orchestrator (Airflow, Dagster, Prefect) would add a scheduler, a metadata DB, and a
daemon. That operational surface contradicts the "clone → `make data` → done"
reproducibility the project relies on. The real orchestration need is the eval and CI
gates, already modeled correctly as a CI job.

**When to revisit:** if the KB corpus needs periodic re-ingestion from live
MedlinePlus/openFDA, or if scheduled NPPES monthly refreshes feed a production index,
reach for a lightweight asset orchestrator (Dagster's local-dev and lineage story fits
best) or a managed scheduler / workflow service
([14-deployment-mapping.md](14-deployment-mapping.md)) without standing up Airflow
yourself.

## Deployment mapping

See [14-deployment-mapping.md](14-deployment-mapping.md): stateless service containers,
a managed queue, an external state store, and a model-serving endpoint.

## Build order

Scalability is documented alongside the deployment mapping. See
[13-build-plan.md](13-build-plan.md).

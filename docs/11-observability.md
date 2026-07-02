# 11 — Observability & Cost Accounting

Implements spec §8. Lives in `carenav/telemetry/`. **Cold path — never blocks a turn.**

## Implemented: Tier-1 turn events

`carenav/telemetry` emits **one structured JSON event per served turn** from a FastAPI
background task (after the response is sent). Each event goes to **stdout** (one JSON
line — Railway's log viewer indexes it) and to the **`turn_event` table** in the app's
Postgres (created lazily, checkfirst). Fields: hashed member ref, intent, safety flag,
tier used + per-tier attempts, confidence, cost, latency, citation count, tools run,
and PII **entity counts** from the turn's PiiMap — never question/answer bodies.
Failures are swallowed: the stdout line already carries the data if the DB write fails.
Dashboards run as SQL over `turn_event` (e.g. Grafana with a Postgres datasource).
Tracing (the OTel span tree below) is the next tier and remains planned.

## Tracing

- **One OpenTelemetry span tree per turn**: a span per node, per tool call, per model
  call.
- Span attributes: `tier`, token counts, latency, confidence breakdown, escalation
  decision.

This gives a per-turn picture of where time and tokens went, and why a turn escalated.

## Cost capture

- The **`ModelGateway`** ([06](06-model-tiering.md)) records `input/output tokens ×
  per-model price` for **every** model call.
- Summed per conversation and exported.
- Feeds the latency/cost metrics ([09](09-eval.md)) — `ai_cost_per_conversation` is
  this number, measured.

## Logs

- Structured **JSON**.
- **Redacted bodies only**, with **entity counts** for the PII audit
  ([05-redaction.md](05-redaction.md)).
- No PHI values, ever. `pii_map` is out of band and never logged.

## Dashboards

- p50/p99 latency
- cost/conversation
- tier distribution (% small-model)
- containment
- **gate status over time**

## Invariant

Telemetry export, eval logging, and any dashboard feed run on the **cold path** via the
async queue ([12-scalability.md](12-scalability.md)). Observability must never add
latency to the hot turn-serving path.

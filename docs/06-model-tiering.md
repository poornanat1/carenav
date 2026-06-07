# 06 — Model Tiering, Confidence & Escalation

Implements spec §4.4. Lives in `carenav/models/`.

## The four tiers

| Tier | What | When | Concrete (Mistral) |
|---|---|---|---|
| **Tier 0 — no LLM** | Pure lookups / deterministic intents skip generation entirely | Deterministic answers | — |
| **Tier 1 — small/cheap** | Routing + the majority of response generation | Confidence above bar | **`mistral-small-latest`** |
| **Tier 2 — frontier** | Invoked only when confidence is low | One retry at higher quality | **`mistral-large-latest`** |
| **Tier 3 — human** | Safety escalation, or persistent low confidence on a high-stakes turn | Safety / give-up | Human handoff |

> Provider is **Mistral** (settled, §14). The `ModelGateway` stays provider-agnostic —
> other providers swappable — but Mistral is the default benchmarked pair. See
> [02-tech-stack.md](02-tech-stack.md).

## Composite confidence

`ConfidenceBreakdown` — each component is 0–1, weighted into a single score.

| Component | Definition |
|---|---|
| `intent_conf` | Router top-1 probability / margin. |
| `retrieval_conf` | Max similarity + score spread of RAG hits. |
| `tool_conf` | Did lookups return **all** required fields? |
| `self_eval` | Small model rates its own groundedness 1–5 → normalized. |
| `safety_override` | Emergent signal forces **Tier 3** regardless of the rest. |

## Escalation policy (pseudocode)

```python
if state.safety_flag == "emergent":
    return Tier.HUMAN                       # safety override — no model can contain this

score = weighted_sum(confidence)
bar = TAU_HIGH if state.safety_flag == "urgent" else TAU_LOW

if score >= bar:
    return Tier.SMALL                       # Tier 1 handles it

# retry once at frontier
regenerate_at(Tier.FRONTIER)
if rescore() >= bar:
    return Tier.FRONTIER                    # Tier 2 cleared the bar

return Tier.HUMAN                           # hand off with context
```

Key points:
- `urgent` turns use a **higher** bar (`TAU_HIGH`) — harder to contain, more likely to escalate.
- `emergent` **never** reaches the scoring logic — it short-circuits to human.
- A frontier retry happens **at most once** before human handoff.

## The GEPA story, applied to serving

The eval harness **sweeps `TAU_LOW` / `TAU_HIGH`** and reports the
**quality-vs-cost frontier**: for each threshold, what % of turns the small model
handles and at what task-success / groundedness.

**Headline result to demonstrate:** *the small model handles the large majority of
turns at quality statistically indistinguishable from the frontier model, at a
fraction of the cost.* Report **tier distribution alongside cost/conversation**.

This sweep is produced by `eval/run.py` ([09-eval.md](09-eval.md)).

## ModelGateway responsibilities

A thin abstraction (`carenav/models/`) — **the only place provider SDKs are imported.**

- Provider-agnostic call interface (Mistral default; other providers swappable).
- Per-call **tier + cost capture**: input/output tokens × per-model price.
- **Prompt capture** for the PII-leak gate (cold path, redacted only — see [05](05-redaction.md)).
- At scale: rate-limiting, retries with backoff, semantic cache ([12](12-scalability.md)).
- **Timeout + fallback tier on every call**; hard failure degrades to human handoff.

## Failure posture

A model call that times out or errors does **not** produce a wrong answer — it falls
back to the next tier, and ultimately to **Tier 3 human handoff**. Never degrade to a
guess. (Echoed in [01](01-architecture.md) and [12](12-scalability.md).)

## Implementation status

**`ModelGateway` v1 shipped with M1** (`carenav/models/gateway.py`) — the only module
that imports a provider SDK (Mistral, via API key). It provides the
provider-agnostic `generate()`/`embed()` interface, per-call **token + cost capture** (a
`CostLedger`), **prompt capture** for the PII-leak gate, a per-call **timeout**, and
**retry-with-backoff** on transient 429/5xx. Generation can be stubbed independently of
embeddings (`stub_generation`) for offline/no-quota runs. The tiering/escalation *policy*
(confidence scoring, frontier retry, human handoff) lands in **M4**; the gateway already
records cost per model so the sweep can be computed once eval exists.

**M4 tiering policy shipped** (`carenav/orchestrator/`): `ConfidenceBreakdown`
(intent/retrieval/tool/self-eval, weighted) scored against `TAU_HIGH` (urgent) /
`TAU_LOW`, emergent triage short-circuiting to Tier 3, **at most one** frontier retry,
and human handoff with a structured packet — matching the pseudocode above. Tier-0
keyword fast paths in the router skip the LLM for unambiguous intents.

## Build order

Tiering + escalation is **M4** in the [build plan](13-build-plan.md). The demo is the
threshold-sweep chart: small-model coverage vs quality vs cost.

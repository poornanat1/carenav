# 03 — Orchestrator (Typed Node Pipeline)

Implements spec §4.1. Lives in `carenav/orchestrator/`.

> **Design note.** The orchestrator is a **hand-written, typed Python pipeline** — one
> pure function per node, composed in `run_turn()` ([turn.py](../src/carenav/orchestrator/turn.py)).
> The turn flow is linear with one bounded retry, which keeps each node independently
> unit-testable and the control flow easy to read. Node names follow this doc, so adopting
> a graph framework later (for multi-turn sessions or cyclic ReAct loops) stays mechanical.

## Turn state

Carried across nodes. **PHI lives only in `pii_map`** — never inside `messages`
or `tool_results`.

```python
class TurnState(TypedDict):
    session_id: str
    messages: list[Message]            # redacted text only
    intent: Intent | None
    member_ref: str | None             # opaque session ref, NOT the member_id
    member_context: dict               # redacted, structured
    retrieved: list[Chunk]             # RAG hits with scores + source urls
    tool_results: list[ToolResult]     # redacted
    confidence: ConfidenceBreakdown    # see 06-model-tiering.md
    tier_used: Literal["small", "frontier", "human"]
    step_count: int
    safety_flag: SafetyLevel           # none | urgent | emergent
    escalate: bool
    pii_map: PiiMap                    # OUT OF BAND — never serialized into a prompt
```

> Implementation note: `pii_map` is part of the `TypedDict` for type-checking, but
> serialization/checkpointing must exclude it from anything that becomes prompt or
> log text. See [05-redaction.md](05-redaction.md).

## Nodes & responsibilities

| # | Node | Responsibility |
|---|---|---|
| 1 | `ingest` | Load session, append user turn. |
| 2 | `safety_triage` | Fast classifier over the **raw** turn. `emergent` → jump straight to `escalate_human`. `urgent` raises the confidence bar in `reflect`. |
| 3 | `redact` | Replace all detected PHI in user text + prior context with stable tokens; populate `pii_map`. |
| 4 | `route` | Intent classification (small model or fine-tuned classifier) → select candidate specialist(s). |
| 5 | `plan` | ReAct reasoning step: decide the next tool call (or "ready to answer"). |
| 6 | `tool_exec` | Invoke the chosen specialist agent. **Its output is redacted before re-entering state.** |
| 7 | `reflect` | Assess: do we have the required fields? Compute `confidence`. Loop back to `plan` if more tools needed, bounded by `MAX_STEPS` (default **5**). |
| 8 | `generate` | Compose a grounded answer with inline source citations. Model tier chosen by `confidence`. |
| 9 | `groundedness_check` | Verify each factual claim against `retrieved` / `tool_results`. On failure: **one** regenerate; second failure → `escalate_human`. |
| 10 | `rehydrate` | Map tokens back to PHI for the **user-facing string only**. |
| 11 | `respond` / `escalate_human` | Terminal nodes. `escalate_human` emits a structured handoff packet (redacted summary, suspected intent, what's been gathered). |

## Conditional edges (sketch)

```
safety_triage --emergent--> escalate_human
reflect --more_tools & step<MAX--> plan
reflect --ready--> generate
reflect --low_conf_high_stakes--> escalate_human
groundedness_check --fail x2--> escalate_human
```

## Critical ordering invariants

1. `safety_triage` runs **before** `redact` — it classifies the raw turn so it never
   misses an emergent signal hidden by tokenization. It must **not** persist the raw
   text anywhere downstream.
2. `redact` runs **before** `route` and every model call — the router is a model and
   must only see tokenized text.
3. `tool_exec` output is redacted **before** it re-enters `tool_results`.
4. `rehydrate` is the **only** place tokens become real values, and only on the final
   user-facing string.
5. The `plan ⇄ tool_exec ⇄ reflect` loop is hard-bounded by `MAX_STEPS`. Hitting the
   bound without sufficient confidence routes to `escalate_human`, not to a guess.

## Escalate-human handoff packet

A structured object (not prose) emitted by `escalate_human`:

- `redacted_summary` — what the member asked, tokenized.
- `suspected_intent` — best router guess.
- `gathered` — tool results collected so far (redacted).
- `reason` — one of: `emergent_safety`, `low_conf_high_stakes`, `groundedness_fail`, `max_steps`.
- `safety_flag` — the triage level.

## Implementation status

**M2 + M4 shipped** (`carenav/orchestrator/`), as a typed Python pipeline — one function
per node:
- `route` — deterministic emergent triage + keyword fast paths + small-model intent
  classify ([router.py](../src/carenav/orchestrator/router.py));
- `decompose` — comparatives split into per-subject sub-questions
  ([decompose.py](../src/carenav/orchestrator/decompose.py));
- `plan → tool_exec → reflect` — run the specialist tools a turn needs and wrap their
  structured outputs as **groundable sources**, so member/benefit/claim facts are cited
  `[CHUNK:tool:<name>]` and grounded like KB chunks; `tool_conf` from agent completeness
  ([tools.py](../src/carenav/orchestrator/tools.py));
- `generate` + `groundedness_check` — via the shared grounding loop over tool + KB sources;
- `verify` — cited docs must match the question's subject (fail → escalate);
- composite confidence vs `TAU_HIGH`/`TAU_LOW`, **one frontier retry**, then the structured
  `escalate_human` handoff packet above.

Served over FastAPI (`POST /turn`, [carenav/api/](../src/carenav/api/)). Remaining M3 node —
`redact` — and session persistence extend this pipeline.

## Build order

This pipeline is **M2** in the [build plan](13-build-plan.md). M1 ships a single
RAG agent + grounding before the full orchestrator exists.

# 05 — PII/PHI Redaction Layer

Implements spec §4.3. Lives in `carenav/redaction/`. **This is the security spine of
the design and one of the two hard CI gates.**

## Position

The redaction layer sits between *(user input + tool outputs)* and *(the model
prompt)*. The model — **at any tier** — only ever sees tokenized text.

```
user input ─┐
            ├─► [ REDACTION ] ─► tokenized text ─► model prompt
tool output ┘                         │
                                      └─► pii_map  (out of band, never in a prompt)
```

## Detection — defense in depth

Three independent layers; an entity caught by any of them is redacted.

| Layer | Catches | Mechanism |
|---|---|---|
| **Deterministic / field-based** | Data *we* introduced — values pulled from known PHI fields of a looked-up record (name, DOB, address, member_id, phone, email, MRN) | Exact / structured match. **Highest precision.** |
| **Model-based NER** | Free-text PHI the *user* typed ("my name is Jordan and my DOB is…") | Presidio + spaCy |
| **Pattern-based** | Format-recognizable identifiers | Regex: SSN-like, phone, email, member-id |

The field-based layer is the most important: because the system itself injects member
records into context, those known fields can be redacted with certainty before any
NER/regex guesswork is needed.

## Tokenization

Each entity → a **stable placeholder scoped to the session**:

```
[MEMBER_NAME]   [DOB_1]   [ADDR_1]   [MEMBER_ID]   [PHONE_1]   ...
```

- Stable within a session so the model can reason about "the same person" coherently.
- The reversible map (`pii_map`) is stored **out of band** in the session store.
- `pii_map` is **never** serialized into any prompt or log body.

## Rehydration

Only the **final user-facing response string** is rehydrated (tokens → real values).
Internal logs, traces, and graph state store **redacted text + entity counts**, never
values. See [03-orchestrator.md](03-orchestrator.md) — the `rehydrate` node is the
single point where this happens.

## Audit

Every detection is logged as `(type, source, position)` — **not value**.

- `type` — entity class (e.g. `DOB`, `MEMBER_NAME`).
- `source` — `user_text` | `tool_output` | `prior_context`.
- `position` — span offset, for debugging coverage.

## The hard gate

The eval harness asserts **zero unredacted PHI patterns ever appear in captured model
inputs** ([09-eval.md](09-eval.md)). This is a **hard CI gate: PII-leakage rate must
be 0.** A regression blocks merge regardless of any other metric.

Implementation requirement: the model gateway ([06](06-model-tiering.md)) must
**capture every outbound prompt** so the eval can scan it. Capture is on the cold path
and must store redacted text only.

## Build order

Redaction is **M3** in the [build plan](13-build-plan.md). The demo for M3 is:
*show a captured model input, fully tokenized, with a clean audit log.*

## Managed-service analog

A managed cloud DLP / sensitive-data service is the direct analog to Presidio — see
[14-deployment-mapping.md](14-deployment-mapping.md).

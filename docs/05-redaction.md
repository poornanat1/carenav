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
| **Fine-tuned model** | Free-text PHI the *user* typed ("my name is Jordan and my DOB is…"), third-party names, provider mentions, reformatted DOBs | Fireworks supervised fine-tune returning copied entity values; offsets are resolved locally |
| **Pattern-based** | Format-recognizable identifiers | Regex: SSN-like, phone, email, member-id |

The field-based layer is the most important: because the system itself injects member
records into context, those known fields can be redacted with certainty before any
NER/regex guesswork is needed.

## Fine-tuned Detector

Layer 2 is a Fireworks LoRA fine-tune trained from generated Synthea-derived PII
examples. It is intentionally an extractor, not a classifier: it returns JSON entities
like `{"text": "Jordan Reyes", "label": "NAME"}` copied from the raw input string.
The gateway maps those copied values back to character offsets before tokenization. This
avoids asking the model to count characters, which was the main recall/F1 failure mode
in the first offset-based fine-tune.

The operational flow is:

1. `make pii-corpus` builds train/eval JSONL examples under `data_artifacts/pii/`.
2. `make train-pii` uploads Fireworks datasets and creates a supervised fine-tuning job.
3. Deploy the resulting model as a LoRA on a base-model deployment with addons enabled.
4. Set `PII_MODEL` to the Fireworks route:
   `<fine_tuned_model>#<deployment>`.

The current deployed value-copy model scored 1.00 precision / 1.00 recall / 1.00 F1 on
the regenerated 1,218-example held-out PII split (`python -m eval.pii.evaluate
--concurrency 8`). The prompted base-model baseline scored 0.00 on the same extraction
contract, so the fine-tune is carrying the model layer.

Current provider settings live in `.env.example`: Fireworks handles generation and PII
fine-tuning; Mistral remains the embedding provider. If `PII_MODEL` or the provider
call is unavailable, the detector fails closed by contributing no layer-2 spans while
field matching and regex continue to enforce the PII-leak gate.

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

The redaction demo is: *show a captured model input, fully tokenized, with a clean audit log.*

## Managed-service analog

A managed cloud DLP / sensitive-data service is the direct analog to Presidio — see
[14-deployment-mapping.md](14-deployment-mapping.md).

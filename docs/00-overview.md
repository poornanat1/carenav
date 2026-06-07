# 00 — Overview

## One-liner

A production-grade, multi-agent conversational assistant that helps health-plan
members with coverage, benefits, claims, provider search, and medication info —
with a PII-redaction security layer, tiered-model cost optimization, and an
eval-driven quality bar.

## Why this domain

It is the richest publicly available data environment for the architecture:

- **MITRE Synthea** generates lifetime synthetic patient records, claims, and FHIR
  bundles — "realistic but not real," free of privacy restrictions.
- **NPPES** is a real, downloadable U.S. provider directory.
- **openFDA / MedlinePlus / CMS SBC** documents supply the RAG corpus.

Synthetic-but-realistic PHI lets the redaction layer be validated on data shaped
exactly like the real thing, with **zero compliance risk**.

## Scope — in-scope intents (the "jobs")

| Intent | Example |
|---|---|
| **Coverage check** | "Is an MRI covered? What's my copay to see a specialist?" |
| **Benefits / accumulators** | "Have I met my deductible? Is my plan active this year?" |
| **Claims** | "Was my last claim paid? Why was claim X denied?" |
| **Provider search** | "Find an in-network endocrinologist near 07302 accepting new patients." |
| **Medication info** | "What are the common side effects of metformin?" (grounded to drug labels) |
| **Self-care guidance** | Low-acuity symptom info from a vetted KB. |
| **Triage routing** | Recognize urgency and route correctly. |

## Out of scope (hard boundaries)

- **No diagnosis, no treatment decisions, no dosing advice.** These are declined and redirected.
- **No PHI ever sent to a model in the clear.** See [05-redaction.md](05-redaction.md).
- **Emergent symptoms are never "contained"** — they escalate to a human/clinician immediately.

## The safety boundary (the spine of the design)

The system has **three escalation tiers**, and the highest is **human handoff**.
The point of the tiered design is *not only* cost — it is that low confidence on a
high-stakes turn, or any emergent-symptom signal, routes to a human.

This makes escalation logic a **safety mechanism, not just a savings lever**, and it
is what keeps "containment rate" honest in a health context (see
[09-eval.md](09-eval.md#62-metrics)).

## How this maps to what the role grades

| Role topic | Where it lives |
|---|---|
| Conversational / agentic AI | Typed orchestrator pipeline + tool-using specialist agents ([03](03-orchestrator.md), [04](04-agents.md)) |
| Security / protect sensitive client data | PII/PHI redaction layer; model never sees raw PHI ([05](05-redaction.md)) |
| Performance & cost optimization | Tiered models + confidence-gated escalation; measured cost/conversation & p50/p99 ([06](06-model-tiering.md), [11](11-observability.md)) |
| Operational excellence / eval | CUJ suite: task success, groundedness, containment, safety, PII-leak; CI-gated ([09](09-eval.md)) |
| Scalability (10k internal → millions external) | Stateless services + queue; horizontal scale story ([12](12-scalability.md)) |
| Model integration | Provider-agnostic model gateway ([06](06-model-tiering.md)) |
| System design + Python fluency | The whole thing, in Python ([01](01-architecture.md)) |
| Deployment mapping | [14-deployment-mapping.md](14-deployment-mapping.md) — core stays cloud-agnostic |

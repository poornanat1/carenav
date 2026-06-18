# 00 — Overview

## What it is

A tool-using conversational assistant for health-plan members. It answers questions
about coverage, benefits, claims, provider search, and medications, with a PII-redaction
layer, tiered models for cost, and an eval-driven quality bar.

## Why this domain

Health benefits offer the richest public data environment for this architecture:

- **MITRE Synthea** generates lifetime synthetic patient records, claims, and FHIR
  bundles — realistic but not real, and free of privacy restrictions.
- **NPPES** is a real, downloadable U.S. provider directory.
- **openFDA, MedlinePlus, and CMS SBC** documents supply the RAG corpus.

Synthetic-but-realistic data lets the redaction layer be validated on records shaped
exactly like real PHI, with no compliance risk.

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

## The safety boundary

The system has three escalation tiers, and the highest is a human handoff. Tiering is not
only about cost. Low confidence on a high-stakes turn, or any emergent-symptom signal,
routes to a human. That makes escalation a safety mechanism, not just a savings lever, and
it keeps "containment rate" honest in a health context (see
[09-eval.md](09-eval.md#62-metrics)).

## Where each concern lives

| Concern | Where |
|---|---|
| Conversational flow | Typed orchestrator pipeline + specialist tools ([03](03-orchestrator.md), [04](04-agents.md)) |
| Protecting sensitive data | PII/PHI redaction; the model never sees raw PHI ([05](05-redaction.md)) |
| Cost and performance | Tiered models + confidence-gated escalation ([06](06-model-tiering.md), [11](11-observability.md)) |
| Quality and safety gates | CUJ eval suite, CI-enforced ([09](09-eval.md)) |
| Scale | Stateless services + queue ([12](12-scalability.md)) |
| Model integration | Provider-agnostic model gateway ([06](06-model-tiering.md)) |
| Deployment | Cloud-agnostic core ([14-deployment-mapping.md](14-deployment-mapping.md)) |

# 08 — Data Model & Ingestion Pipeline

Implements spec §5. Lives in `carenav/data/`.

## Core entities (abridged)

`*` marks a PHI field.

| Entity | Fields |
|---|---|
| **Member** | `member_id`, `name*`, `dob*`, `address*`, `plan_id`, `eligibility_status`, `coverage_start`, `coverage_end` |
| **Plan** | `plan_id`, `name`, `deductible`, `oop_max`, `copays_by_category`, `coinsurance` |
| **Accumulator** | `member_id`, `plan_year`, `deductible_met`, `oop_met` |
| **Claim** | `claim_id`, `member_id`, `provider_npi`, `service_code`, `billed`, `allowed`, `paid`, `member_responsibility`, `status`, `denial_reason` |
| **Condition** | `member_id`, `icd10`, `display`, `clinical_status`, `onset_date`, `kb_topic` — a member's diagnosis (FHIR Condition-shaped). `kb_topic` ties the diagnosis to a KB corpus doc so the structured data and retrieval line up. Synthetic, never real PHI. |
| **BenefitRule** | `service_code \| category`, `covered`, `copay`, `coinsurance`, `prior_auth_required`, `notes` |
| **Provider** | `npi`, `name`, `taxonomy/specialty`, `address`, `accepting_new` (from NPPES) |
| **KBDoc / Chunk** | `doc_id`, `chunk_id`, `text`, `embedding`, `source_url`, `title`, `last_reviewed`, `source_type` |

> The PHI fields (`name`, `dob`, `address`, `member_id`) are exactly the values the
> **deterministic redaction layer** keys on ([05-redaction.md](05-redaction.md)).

## Ingestion pipeline

All steps run under `make data`. They are idempotent and scripted, and assert row
counts so a fresh clone reproduces the dataset.

| Step | Action | Source → target |
|---|---|---|
| 1 | **Generate members/claims/conditions** | Run Synthea (`scripts/run_synthea.sh`, needs Java) → export CSV + FHIR → load into Postgres. Patients become `Member`s (assigned a CareNav plan round-robin); encounters become `Claim`s; `Accumulator`s are derived from claim cost-sharing; SNOMED-coded diagnoses become `Condition`s. Conditions that match a covered KB topic are linked via `kb_topic` so the patient data and the knowledge base line up. There is no synthetic fallback: ingest errors if the Synthea CSVs are absent. The FHIR bundle is an on-ramp for any FHIR store ([14](14-deployment-mapping.md)). |
| 2 | **Providers** | Download the NPPES monthly file → filter to relevant taxonomies/states → load `Provider`. Build a synthetic `plan_network` join table marking a subset in-network. |
| 3 | **Benefit rules** | Author a small, plausible benefit table per plan. This is the one hand-built artifact; keep it small and documented. |
| 4 | **KB corpus** | Fetch curated MedlinePlus/CDC pages + openFDA labels + sample SBC PDFs → clean → chunk → embed → load vector store ([07](07-rag.md)). |

## Idempotency & reproducibility requirement

`make data` on a fresh clone must reproduce the same dataset, with asserted row
counts at each step. Re-running must not duplicate rows. This is what makes the
demo reproducible and the eval deterministic.

## Stores

- **Structured tables** (`Member`, `Plan`, `Accumulator`, `Claim`, `BenefitRule`,
  `Provider`, `plan_network`): Postgres.
- **Vector store** (`KBDoc`/`Chunk` embeddings): pgvector on the same Postgres engine.

See [02-tech-stack.md](02-tech-stack.md) for the settled DB decision.

## Build order

The data pipeline is the foundation. Demo: `make data` → populated Postgres + vector
store with asserted row counts. See [13-build-plan.md](13-build-plan.md).

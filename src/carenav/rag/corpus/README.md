# KB corpus

The reproducible knowledge base for CareNav's RAG layer (docs/07-rag.md). These are
**curated, condensed excerpts** of public health and plan-coverage information, vendored
into the repo so `make data` builds the vector store fully offline on a fresh clone.

Each file is one source document: YAML frontmatter (`doc_id`, `source_type`, `title`,
`source_url`, `last_reviewed`) followed by a heading-structured body. The ingest
(`carenav/rag/ingest_kb.py`) chunks each file heading-scoped, embeds the chunks, and
loads them into pgvector.

## Source types

| Dir | `source_type` | Origin (public) | Retrieval intent |
|---|---|---|---|
| `consumer_health/` | `consumer_health` | MedlinePlus / CDC consumer-health pages | condition basics, self-care |
| `drug_label/` | `drug_label` | openFDA / MedlinePlus drug information | medication info |
| `sbc/` | `sbc` | CMS Summary-of-Benefits-and-Coverage + Uniform Glossary concepts | plan coverage/policy |

The corpus is sized to cover **every clinical condition the real Synthea patient data
contains**. Synthea emits ~200 distinct clinical diagnoses; rather than one doc per code,
conditions are grouped into ~30 clinical **topics** (e.g. all the sinusitis / pharyngitis
/ bronchitis codes → one "upper respiratory infections" doc; all the dental codes → "dental
and oral health"; the CKD stages → "chronic kidney disease"). `carenav/data/condition_topics.py`
classifies every diagnosis into one of these topics, and each topic has a consumer-health
doc here, so **100% of clinical patient-conditions line up with retrievable KB content**.
Non-clinical Synthea findings (employment, education, social status) are intentionally not
covered.

The **drug labels** are covered the same way: Synthea prescribes ~190 distinct medications,
grouped into ~25 drug-class **topics** (e.g. all the ACE inhibitors / ARBs / beta blockers /
calcium-channel blockers → one "blood pressure medications" doc; every "-statin" → "statins";
opioids, NSAIDs, antibiotics, chemotherapy agents, etc.). `carenav/data/drug_topics.py`
classifies every prescription into a topic, and each topic has a `drug_label` doc here, so
**100% of prescriptions line up with retrievable drug information**. Single-drug labels keep
the `openfda-` doc_id prefix; drug-class docs use `mplus-`.

The corpus also includes coverage concepts (prior authorization, preventive vs. diagnostic
care) plus the synthetic Gold/Silver SBCs.

The `condition` table's `kb_topic` records each diagnosis's topic, so a member's record and
the knowledge base are joined: a patient diagnosed with any covered condition — or taking
any covered medication — can be answered from the matching doc. Coverage for both is
asserted by tests (`tests/test_condition_topics.py`, `tests/test_drug_topics.py`) against
vendored snapshots of the Synthea condition and medication universe.

`source_type` is the per-intent retrieval filter: medication intents only hit
`drug_label` chunks, coverage intents only hit `sbc` chunks. That is both a quality and
a safety boundary (no drug-label text leaking into a coverage answer).

## Provenance & freshness

The `source_url` in each file's frontmatter records where the real content comes from.
The SBC docs are **synthetic examples** formatted to the federal SBC template, with
numbers matching the demo plans (Bronze/Silver/Gold) — labeled as such in-body. The
consumer-health and drug-label excerpts are condensed from the cited public sources.

To refresh from upstream (optional; requires network), see
[scripts/fetch_kb.sh](../../../scripts/fetch_kb.sh). It documents the canonical URLs and
APIs; the committed `.md` files remain the source of truth so the build stays
deterministic.

> Not medical advice. This corpus exists to exercise grounded retrieval and citation,
> not to provide clinical guidance.

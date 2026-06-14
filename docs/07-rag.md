# 07 — RAG Subsystem

Implements spec §4.5. Lives in `carenav/rag/`.

## Corpus

| Source | Use | Per-chunk metadata |
|---|---|---|
| **MedlinePlus / CDC** consumer-health pages | Self-care, condition basics | `source_url`, `title`, `last_reviewed` |
| **openFDA** drug labels | Medication info | same |
| **CMS Summary-of-Benefits-and-Coverage (SBC)** docs | Plan policy | same |

Every chunk stores `source_url`, `title`, `last_reviewed`, and a `source_type` (for
per-intent filtering).

## Chunking

- **Structure-aware**: heading-scoped, ~512-token chunks with overlap.
- Keep the **section path** as metadata for citation.

## Retrieval

- **Top-k** (default **5**) by cosine similarity.
- Optional rerank.
- **Filter by `source_type` per intent** — e.g. medication intents only hit drug-label
  chunks; coverage intents only hit SBC chunks. This is both a quality and a safety
  measure (no drug-label text leaking into a coverage answer).

## Grounding contract

This is what makes answers trustworthy and is enforced by the orchestrator:

1. The `generate` node **must cite chunk IDs for every factual claim**.
2. `groundedness_check` validates **claim-level entailment** against the cited chunks.
3. **Uncited claims are stripped or trigger regeneration.**
4. Second groundedness failure → `escalate_human` ([03-orchestrator.md](03-orchestrator.md)).

`retrieval_conf` (max similarity + score spread) feeds the confidence breakdown
([06-model-tiering.md](06-model-tiering.md)).

## Vector store

**pgvector on Postgres** (settled, §14). Retrieval is the single `hybrid_search` SQL
function — vector ANN + weighted full-text in one CTE pipeline. 

## Injection defense

KB docs are **untrusted content**. Retrieved text is treated as **data, never as
instructions** — the orchestrator must never let chunk content alter tool-use or
policy. Tested by **CUJ-10** ([09-eval.md](09-eval.md)).

## Implementation

The KB corpus + vector store landed first as the retrieval foundation:

- **Corpus** — `carenav/rag/corpus/` holds curated, condensed source docs as Markdown
  with frontmatter (`doc_id`, `source_type`, `title`, `source_url`, `last_reviewed`),
  grouped by `source_type` (`consumer_health` / `drug_label` / `sbc`). Vendored so the
  build is offline + reproducible; `scripts/fetch_kb.sh` records upstream provenance.
- **Chunking** — `carenav/rag/chunking.py`: heading-scoped, ~512-token windows with
  sentence overlap, keeping the section path for citation.
- **Embeddings** — `carenav/rag/embeddings.py`: always real Mistral
  (`mistral-embed`), delegated to the `ModelGateway` (the only place the provider
  SDK is imported). A single `MISTRAL_API_KEY` is required. `mistral-embed` is a fixed
  **1024-dim symmetric** model — it has no asymmetric task types, so corpus chunks and
  queries embed identically — and the 1024 dimensions match the pgvector column.
- **Ingest** — `carenav/rag/ingest_kb.py` (the `kb` pipeline stage): corpus → chunk →
  embed → pgvector, idempotent, with row-count assertions in the data pipeline.
- **Retrieval** — consolidated in `carenav/rag/sql/hybrid_search.sql`, ONE Postgres
  function (a CTE pipeline) installed by `init_schema`: pgvector ANN candidates →
  **hybrid scoring** (cosine + weighted `ts_rank`, title ≫ body, so named entities like
  "Silver plan" or a drug name anchor lexically) → top-k → a **doc-level relevance
  prune** that drops off-subject intruder docs. Chunks are embedded **with their doc
  title + section path** (contextual embeddings) so generically-worded sections don't
  bleed across sibling docs. `carenav/rag/retrieval.py` is a thin caller of the SQL
  function. `retrieval_conf()` returns max-similarity-tempered-by-spread.

### Agent + grounding contract

- **Agent** — `carenav/rag/agent.py`: `retrieve → generate → groundedness_check →
  (regenerate once) → answer | escalate`, returning a typed `RagAnswer` (cleaned text,
  resolved `citations`, `grounded`, `escalated`, `retrieval_conf`, captured `cost_usd`).
- **Generate** — `carenav/rag/prompts.py`: a strict system contract instructs the model
  to cite `[CHUNK:<id>]` after every factual sentence and to treat sources as data, not
  instructions (injection defense). Goes through the `ModelGateway`.
- **groundedness_check** — `carenav/rag/groundedness.py`: splits the answer into
  sentences (keeping trailing citations attached), and for each factual claim verifies
  the citation names a retrieved chunk AND that the chunk entails the claim (v1 lexical
  proxy; LLM-judge entailment is the eval-harness upgrade). Uncited/unsupported claims are
  stripped; if the answer isn't grounded, **one** regenerate, then escalate.

**RAG demo (live model):** *"What are the side effects of metformin?"* → a grounded
answer with every sentence citing the metformin drug-label chunk; *"prior auth for an
MRI?"* → "Yes…" citing both plan SBCs.

## Build order

A single RAG agent + grounding is the first credible demo: *ask a medication question,
get a cited, grounded answer.* See [13-build-plan.md](13-build-plan.md).

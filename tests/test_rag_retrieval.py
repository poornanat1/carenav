"""End-to-end retrieval against the live Postgres KB (real Mistral query embeddings).

Reads the already-ingested corpus (run `make data` / the kb stage first) and exercises the
hybrid_search function: per-intent source_type filtering, ranking, and citation metadata.
Read-only — no ingest, no teardown. Requires Postgres + a MISTRAL_API_KEY.
"""

from tests.conftest import requires_db, requires_mistral

pytestmark = [requires_db, requires_mistral]


def _retrieval():
    from carenav.rag import retrieval

    return retrieval


def test_corpus_is_loaded():
    from sqlalchemy import func, select

    from carenav.data.db import session_scope
    from carenav.rag.models import KBChunk, KBDoc

    with session_scope() as s:
        docs = s.scalar(select(func.count()).select_from(KBDoc))
        chunks = s.scalar(select(func.count()).select_from(KBChunk))
    assert docs >= 15, "run the kb ingest stage first (make data)"
    assert chunks >= 40


def test_medication_intent_only_returns_drug_labels():
    hits = _retrieval().retrieve(
        "What are the side effects of metformin?", intent="medication", k=5
    )
    assert hits
    assert {h.source_type for h in hits} == {"drug_label"}


def test_coverage_intent_only_returns_sbc():
    hits = _retrieval().retrieve(
        "Is an MRI covered and do I need prior auth?", intent="coverage", k=5
    )
    assert hits
    assert {h.source_type for h in hits} == {"sbc"}


def test_top_hit_is_relevant():
    hits = _retrieval().retrieve("symptoms of type 2 diabetes", intent="self_care", k=3)
    assert hits[0].doc_id == "mplus-type-2-diabetes"


def test_hits_carry_citation_metadata():
    hits = _retrieval().retrieve("metformin dosage", intent="medication", k=3)
    h = hits[0]
    assert h.chunk_id and h.source_url and h.title
    assert h.section_path  # heading path for the citation


def test_no_intent_searches_whole_kb():
    hits = _retrieval().retrieve("blood pressure", k=10)
    assert hits
    assert len({h.source_type for h in hits}) >= 1


def test_retrieval_conf_in_range():
    retrieval = _retrieval()
    hits = retrieval.retrieve("lisinopril", intent="medication", k=5)
    conf = retrieval.retrieval_conf(hits)
    assert 0.0 <= conf <= 1.0
    assert retrieval.retrieval_conf([]) == 0.0

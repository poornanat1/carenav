"""RAG agent end-to-end against the live Postgres KB with real Mistral (embed + generate).

Reads the already-ingested corpus (run the kb stage first). Requires Postgres + a
MISTRAL_API_KEY with generation quota. Assertions are structural only (grounded/escalated,
citations resolve, cited ids appear in the answer) — never exact LLM wording.
"""

from tests.conftest import requires_db, requires_generation

pytestmark = [requires_db, requires_generation]


def test_medication_answer_is_grounded_and_cited():
    from carenav.rag.agent import answer_question

    a = answer_question("What are the side effects of metformin?", intent="medication")
    assert a.grounded and not a.escalated
    assert a.answer
    assert a.citations
    # Citations stay within drug-label docs (per-intent source_type filter held). Build the
    # set of drug-label doc_ids from the corpus rather than assuming a filename prefix.
    from carenav.rag.corpus_loader import load_corpus

    drug_doc_ids = {d.doc_id for d in load_corpus() if d.source_type == "drug_label"}
    for c in a.citations:
        doc_id = c.chunk_id.rsplit("::", 1)[0]
        assert doc_id in drug_doc_ids, f"citation {c.chunk_id} is not a drug-label chunk"
    # Every cited id actually appears in the answer text.
    for c in a.citations:
        assert f"[CHUNK:{c.chunk_id}]" in a.answer


def test_cost_is_captured():
    from carenav.models import ModelGateway
    from carenav.rag.agent import answer_question

    gw = ModelGateway()
    answer_question("Is lisinopril safe during pregnancy?", intent="medication", gateway=gw)
    # Both the query embedding and the generation call are recorded with real cost.
    assert any(c.kind == "embed" for c in gw.ledger.calls)
    assert any(c.kind == "generate" for c in gw.ledger.calls)
    assert gw.ledger.total_cost_usd > 0


def test_no_retrieval_escalates():
    from carenav.rag.agent import answer_question

    # An off-domain query under a strict intent filter yields weak/no useful hits but
    # should never fabricate; with hits present it still must stay grounded or escalate.
    a = answer_question("xyzzy nonsense token", intent="medication")
    assert a.grounded or a.escalated  # never a non-grounded, non-escalated answer

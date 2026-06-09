"""Groundedness check unit tests — pure logic, no model/DB/key required."""

from carenav.rag import groundedness
from carenav.rag.retrieval import Hit


def _hit(chunk_id: str, text: str) -> Hit:
    return Hit(
        chunk_id=chunk_id, doc_id="d", source_type="drug_label", title="T",
        source_url="u", last_reviewed=None, section_path="S", text=text, score=0.9,
    )


HITS = [
    _hit("c1", "Metformin can cause diarrhea, nausea, and upset stomach."),
    _hit("c2", "Lisinopril may cause a dry cough and dizziness."),
]


def test_cited_and_entailed_claim_passes():
    ans = "Metformin can cause nausea and diarrhea. [CHUNK:c1]"
    r = groundedness.check(ans, HITS)
    assert r.grounded
    assert r.cleaned_answer == ans


def test_uncited_claim_fails_and_is_stripped():
    ans = "Metformin cures diabetes permanently."
    r = groundedness.check(ans, HITS)
    assert not r.grounded
    assert "cures diabetes" not in r.cleaned_answer


def test_citation_to_unknown_chunk_fails():
    ans = "Metformin can cause nausea. [CHUNK:does-not-exist]"
    r = groundedness.check(ans, HITS)
    assert not r.grounded


def test_cited_but_unentailed_claim_fails():
    # Cites a real chunk, but the claim's content isn't supported by that chunk.
    ans = "Lisinopril is an antibiotic for infections. [CHUNK:c2]"
    r = groundedness.check(ans, HITS)
    assert not r.grounded


def test_hedge_sentence_needs_no_citation():
    ans = "The sources do not contain information to answer that."
    r = groundedness.check(ans, HITS)
    assert r.grounded  # a no-info hedge is grounded (nothing to support)


def test_trailing_citation_stays_attached_to_its_sentence():
    # Period before the citation must not orphan the citation onto its own "sentence".
    ans = "Metformin can cause nausea and diarrhea. [CHUNK:c1]"
    r = groundedness.check(ans, HITS)
    claim_verdicts = [v for v in r.verdicts if v.is_claim]
    assert len(claim_verdicts) == 1
    assert claim_verdicts[0].valid_citation and claim_verdicts[0].ok


def test_mixed_answer_keeps_good_drops_bad():
    ans = "Metformin can cause nausea. [CHUNK:c1] It also reverses aging."
    r = groundedness.check(ans, HITS)
    assert not r.grounded
    assert "nausea" in r.cleaned_answer
    assert "aging" not in r.cleaned_answer

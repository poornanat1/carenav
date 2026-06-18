"""LLM query rewrite for retrieval (docs/07-rag.md).

The raw member question is tuned for a human, not for hybrid search: filler words
("what are the common ... ?") dilute the query embedding, and *class* terms ("a statin",
"an SSRI", "a beta blocker") don't lexically or semantically match the *specific* drug
documents in the KB (the corpus has `atorvastatin`, not a generic "statins" page). The
result is that a clearly answerable question retrieves the wrong-class chunks, the answer
fails the groundedness check, and the turn escalates.

This module asks a small model to distill the question into a focused retrieval query:
keep the salient clinical entities, and expand a drug *class* to a representative member
of that class so the specific drug-label chunk surfaces. It runs before embedding and
fails OPEN — any error or empty result falls back to the original question, so retrieval
is never worse than before.
"""

from __future__ import annotations

from carenav.models import ModelGateway

_REWRITE_PROMPT = """Rewrite a member's health question into a short search query for a \
medical knowledge base.

Rules:
- Keep the key clinical entities: drug names, conditions, body systems, the aspect asked \
about (e.g. "side effects", "interactions", "dosing").
- Drop filler words ("what are the", "can you tell me", "common", "please").
- If the question names a drug CLASS rather than a specific drug, expand it to a common \
representative drug in that class so the specific drug label is found. Examples:
  - "statin" -> "statin atorvastatin"
  - "SSRI" -> "SSRI sertraline"
  - "beta blocker" -> "beta blocker metoprolol"
  - "ACE inhibitor" -> "ACE inhibitor lisinopril"
  - "PPI" / "proton pump inhibitor" -> "proton pump inhibitor omeprazole"
  - "biguanide" -> "biguanide metformin"
- Output ONLY the rewritten query, no quotes or explanation.

Question: {question}

Search query:"""

# Don't let the model run away; a focused query is short.
_MAX_QUERY_LEN = 160


def rewrite_for_retrieval(question: str, gateway: ModelGateway | None = None) -> str:
    """Return a retrieval-tuned query for `question`, or `question` itself on any failure.

    Class terms are expanded to a representative drug so specific drug-label chunks
    surface. Always falls back to the original question (fail-open) so retrieval can only
    improve, never break.
    """
    if gateway is None:
        return question
    try:
        raw = gateway.generate(
            _REWRITE_PROMPT.format(question=question),
            label="rag.query_rewrite",
        ).text
    except Exception:
        return question
    rewritten = raw.strip().strip("\"'`").splitlines()[0].strip() if raw.strip() else ""
    if not rewritten or len(rewritten) > _MAX_QUERY_LEN:
        return question
    return rewritten

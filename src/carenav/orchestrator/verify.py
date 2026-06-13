"""verify node — post-answer citation-subject check (the #34 class of failure).

Hybrid lexical retrieval makes wrong-sibling citations rare; this is the belt to that
suspenders: one small-model yes/no asking whether the cited documents' titles are
plausibly the right sources for the question. A mismatch fails SAFE (escalate), never
silently ships a mis-attributed answer. Skipped when there are no citations.
"""

from __future__ import annotations

from carenav.models import ModelGateway
from carenav.rag.agent import RagAnswer

_VERIFY_PROMPT = """A member asked: {question}

The drafted answer cites only these source documents:
{titles}

Could these documents plausibly be the right sources for that question? Consider whether
they are about the same drug / condition / plan the member named. Reply with ONLY "yes"
or "no"."""


def verify_citations(
    question: str, answers: list[RagAnswer], gateway: ModelGateway
) -> bool:
    """True if the citations plausibly match the question's subject (or nothing to check)."""
    titles = sorted({c.title for a in answers for c in a.citations})
    if not titles:
        return True
    raw = gateway.generate(
        _VERIFY_PROMPT.format(question=question, titles="\n".join(f"- {t}" for t in titles)),
        label="orchestrator.verify",
    ).text.strip().lower()
    return not raw.startswith("no")

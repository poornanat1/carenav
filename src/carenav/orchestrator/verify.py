"""verify node — post-answer citation-subject check (the #34 class of failure).

Hybrid lexical retrieval makes wrong-sibling citations rare; this is the belt to that
suspenders: one small-model yes/no asking whether the cited documents' titles are
plausibly the right sources for the question. A mismatch fails SAFE (escalate), never
silently ships a mis-attributed answer. Skipped when there are no citations.
"""

from __future__ import annotations

import re

from carenav.models import ModelGateway
from carenav.rag.agent import RagAnswer

_VERIFY_PROMPT = """A member asked: {question}

The drafted answer cites these source excerpts:
{sources}

Could these sources plausibly be the right sources for that question? Consider whether
the source title or excerpt covers the same drug / condition / plan the member named.
Reply with ONLY "yes" or "no"."""

_STOPWORDS = {
    "what", "whats", "about", "does", "have", "with", "from", "this", "that", "member",
    "patient", "plan", "care", "covered", "under", "question", "please", "explain",
}


def _content_terms(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 5 and word not in _STOPWORDS
    }


def _source_blocks(answers: list[RagAnswer]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    seen: set[str] = set()
    for answer in answers:
        cited_ids = {citation.chunk_id for citation in answer.citations}
        for hit in answer.hits:
            if hit.chunk_id in cited_ids and hit.chunk_id not in seen:
                blocks.append((hit.title, hit.text[:700]))
                seen.add(hit.chunk_id)
    return blocks


def verify_citations(
    question: str, answers: list[RagAnswer], gateway: ModelGateway
) -> bool:
    """True if the citations plausibly match the question's subject (or nothing to check)."""
    titles = sorted({c.title for a in answers for c in a.citations})
    if not titles:
        return True
    blocks = _source_blocks(answers)
    question_terms = _content_terms(question)
    if question_terms and any(
        question_terms & _content_terms(f"{title} {excerpt}") for title, excerpt in blocks
    ):
        return True
    sources = "\n".join(f"- {title}: {excerpt}" for title, excerpt in blocks)
    if not sources:
        sources = "\n".join(f"- {title}" for title in titles)
    raw = gateway.generate(
        _VERIFY_PROMPT.format(question=question, sources=sources),
        label="orchestrator.verify",
    ).text.strip().lower()
    return not raw.startswith("no")

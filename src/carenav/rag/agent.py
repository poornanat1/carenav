"""RAG agent — the grounded Q&A loop (docs/07, docs/13).

retrieve → generate (cited) → groundedness_check → (regenerate once) → answer | escalate.

This is the single-agent grounding loop that ships before the full orchestrator exists.
It enforces the grounding contract end to end:

  * generate is prompted to cite [CHUNK:<id>] for every factual claim;
  * groundedness_check verifies each claim is validly cited AND entailed by the chunk;
  * on failure, ONE regenerate naming the problem; a second failure escalates to a human
    (no guess), returning a structured handoff reason.

All model access goes through the ModelGateway, so token/cost is captured for every call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from carenav.config import settings
from carenav.models import ModelGateway
from carenav.rag import groundedness, prompts, query_rewrite, retrieval
from carenav.rag.retrieval import Hit


@dataclass
class Citation:
    chunk_id: str
    title: str
    source_url: str
    section_path: str | None


@dataclass
class RagAnswer:
    question: str
    answer: str                       # cleaned, grounded, user-facing (tokenized until rehydrate)
    citations: list[Citation]
    grounded: bool
    escalated: bool
    escalation_reason: str | None     # "groundedness_fail" | "no_retrieval"
    retrieval_conf: float
    attempts: int                     # generate passes used (1 or 2)
    cost_usd: float
    hits: list[Hit] = field(default_factory=list)


def _citations_for(answer: str, hits: list[Hit]) -> list[Citation]:
    """Citations for the chunk ids actually referenced in the final answer text."""
    import re

    cited_ids = set(re.findall(r"\[CHUNK:([^\]]+)\]", answer))
    by_id = {h.chunk_id: h for h in hits}
    out = []
    for cid in cited_ids:
        h = by_id.get(cid)
        if h:
            out.append(Citation(h.chunk_id, h.title, h.source_url, h.section_path))
    return out


def answer_question(
    question: str,
    *,
    intent: str | None = None,
    gateway: ModelGateway | None = None,
    k: int | None = None,
    model: str | None = None,
) -> RagAnswer:
    """Answer a question with a cited, grounded response, or escalate.

    `intent` selects the source_type filter (e.g. "medication" → drug-label chunks).
    `gateway` is reused if provided so cost accrues across calls; otherwise one is made.
    """
    gw = gateway or ModelGateway()
    model = model or settings.model_small

    # Retrieve on an LLM-tuned query (filler dropped, drug classes expanded to a
    # representative drug) so class questions like "side effects of statins" surface the
    # specific drug-label chunks instead of unrelated medication-class docs. Generation
    # and grounding still use the member's original question — only retrieval is rewritten.
    retrieval_query = query_rewrite.rewrite_for_retrieval(question, gateway=gw)
    hits = retrieval.retrieve(retrieval_query, intent=intent, k=k, gateway=gw)
    conf = retrieval.retrieval_conf(hits)

    if not hits:
        # Nothing to ground against — don't let the model invent. Escalate.
        return RagAnswer(
            question=question, answer="", citations=[], grounded=False, escalated=True,
            escalation_reason="no_retrieval", retrieval_conf=conf, attempts=0,
            cost_usd=gw.ledger.total_cost_usd, hits=hits,
        )

    return generate_grounded(question, hits, gateway=gw, model=model, retrieval_conf=conf)


def generate_grounded(
    question: str,
    hits: list[Hit],
    *,
    gateway: ModelGateway,
    model: str | None = None,
    retrieval_conf: float = 1.0,
) -> RagAnswer:
    """The grounding loop over an already-assembled source set.

    `hits` may be KB chunks, tool-result pseudo-chunks (the orchestrator wraps structured
    agent outputs as sources with `tool:` ids), or both — the citation + entailment
    contract is identical either way. generate → check → (regenerate once) → answer|escalate.
    """
    model = model or settings.model_small

    prompt = prompts.build_generate_prompt(question, hits)
    raw = gateway.generate(prompt, model=model, label="rag.generate").text
    result = groundedness.check(raw, hits)
    attempts = 1

    # One regenerate on failure (docs/03: groundedness_check --fail x2--> escalate_human).
    if not result.grounded:
        regen_prompt = prompts.build_regenerate_prompt(question, hits, raw, result.problems)
        raw2 = gateway.generate(regen_prompt, model=model, label="rag.regenerate").text
        result = groundedness.check(raw2, hits)
        attempts = 2

    if not result.grounded:
        return RagAnswer(
            question=question, answer=result.cleaned_answer, citations=[], grounded=False,
            escalated=True, escalation_reason="groundedness_fail",
            retrieval_conf=retrieval_conf, attempts=attempts,
            cost_usd=gateway.ledger.total_cost_usd, hits=hits,
        )

    final = result.cleaned_answer
    return RagAnswer(
        question=question, answer=final, citations=_citations_for(final, hits),
        grounded=True, escalated=False, escalation_reason=None,
        retrieval_conf=retrieval_conf, attempts=attempts,
        cost_usd=gateway.ledger.total_cost_usd, hits=hits,
    )

"""Retrieval: hybrid (vector + lexical) search over KB chunks, per-intent filtered.

All retrieval is the `hybrid_search` Postgres function (carenav/rag/sql/hybrid_search.sql)
— pgvector ANN candidates, hybrid cosine + weighted ts_rank scoring, and a doc-level
relevance prune, as one CTE pipeline. This module is a thin caller.

The `source_type` filter is the per-intent boundary (and a safety boundary): a
medication intent only ever sees drug-label chunks, a coverage intent only SBC chunks.
The mapping lives here so the orchestrator's router can pass an intent straight through.

Each hit carries the citation metadata the grounding contract needs (chunk_id, title,
source_url, section_path) plus the hybrid score. `retrieval_conf()` (max similarity +
score spread) feeds the confidence breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from carenav.config import settings
from carenav.data.db import session_scope
from carenav.rag import embeddings

# Per-intent source_type filter. Intent strings are the router's vocabulary (Day 6);
# kept loose (str keys) so this module does not depend on the orchestrator's Intent enum.
# None => no filter (search the whole KB).
INTENT_SOURCE_TYPES: dict[str, tuple[str, ...]] = {
    "medication": ("drug_label",),
    "coverage": ("sbc",),
    "benefit": ("sbc",),
    "self_care": ("consumer_health",),
    "condition_info": ("consumer_health",),
}


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_id: str
    source_type: str
    title: str
    source_url: str
    last_reviewed: str | None
    section_path: str | None
    text: str
    score: float  # cosine similarity in [-1, 1]


def source_types_for_intent(intent: str | None) -> tuple[str, ...] | None:
    """Resolve an intent to its allowed source_types (None => search everything)."""
    if intent is None:
        return None
    return INTENT_SOURCE_TYPES.get(intent)


def _plan_sbc_doc_id(plan_id: str) -> str | None:
    """Map a plan_id (e.g. PLN-BRONZE) to its plan-specific SBC doc_id (sbc-carenav-bronze).

    Returns None for an unrecognized plan id, in which case no plan-specific SBC is
    assumed and all plan SBCs are filtered out (only plan-agnostic coverage docs remain).
    """
    if not plan_id or not plan_id.upper().startswith("PLN-"):
        return None
    tier = plan_id.split("-", 1)[1].lower()
    return f"sbc-carenav-{tier}"


def _scope_sbc_to_plan(hits: list[Hit], plan_id: str | None) -> list[Hit]:
    """Drop SBC chunks belonging to a DIFFERENT plan than the member's.

    SBC docs encode their plan in the doc_id (`sbc-carenav-<tier>`); plan-agnostic
    coverage basics (e.g. `cms-*`) are kept for every member. Without this, a Bronze
    member's coverage question could be grounded in the Gold or Silver SBC — wrong-plan
    grounding. Non-SBC chunks are untouched.
    """
    if plan_id is None:
        return hits
    own = _plan_sbc_doc_id(plan_id)
    kept: list[Hit] = []
    for h in hits:
        if h.source_type != "sbc":
            kept.append(h)
            continue
        # A plan-specific SBC doc_id looks like `sbc-carenav-<tier>`; keep only the
        # member's own, plus plan-agnostic SBC-type docs (which are not `sbc-carenav-*`).
        if h.doc_id.startswith("sbc-carenav-"):
            if h.doc_id == own:
                kept.append(h)
        else:
            kept.append(h)
    return kept


def retrieve(
    query: str,
    intent: str | None = None,
    k: int | None = None,
    source_types: tuple[str, ...] | None = None,
    gateway=None,
    plan_id: str | None = None,
) -> list[Hit]:
    """Top-k chunks for a query via the `hybrid_search` Postgres function.

    Pass `source_types` to override the intent mapping explicitly. With neither intent
    nor source_types, the whole KB is searched. `gateway` lets the caller's cost ledger
    capture the query-embedding call. The SQL applies hybrid scoring + the doc-level
    relevance prune (carenav/rag/sql/hybrid_search.sql).

    `plan_id` scopes plan-specific SBC chunks to the member's own plan: another plan's SBC
    is never returned (no wrong-plan grounding). When set, we over-fetch then filter so a
    dropped wrong-plan SBC still leaves a full top-k of valid hits.
    """
    k = k or settings.rag_top_k
    if source_types is None:
        source_types = source_types_for_intent(intent)
    # Over-fetch when a plan filter is active so dropping other plans' SBC chunks doesn't
    # starve the result set below k.
    fetch_k = k * 3 if plan_id is not None else k
    query_vec = embeddings.embed_query(query, gateway=gateway)
    qvec = "[" + ",".join(f"{x:g}" for x in query_vec) + "]"  # pgvector literal
    sql = text("""
        SELECT * FROM hybrid_search(
            CAST(:qvec AS vector), :qtext, CAST(:types AS text[]), :k, :margin, :lex_weight)
    """)
    params: dict = {
        "qvec": qvec,
        "qtext": query,
        "types": list(source_types) if source_types else None,
        "k": fetch_k,
        "margin": settings.rag_relevance_margin,
        "lex_weight": settings.rag_lex_weight,
    }
    with session_scope() as session:
        rows = session.execute(sql, params).mappings().all()
    hits = [
        Hit(
            chunk_id=r["chunk_id"], doc_id=r["doc_id"], source_type=r["source_type"],
            title=r["title"], source_url=r["source_url"], last_reviewed=r["last_reviewed"],
            section_path=r["section_path"], text=r["text"], score=float(r["score"]),
        )
        for r in rows
    ]
    if plan_id is not None:
        hits = _scope_sbc_to_plan(hits, plan_id)
    return hits[:k]


def retrieval_conf(hits: list[Hit]) -> float:
    """`retrieval_conf` for the confidence breakdown (docs/06-model-tiering.md).

    Max similarity tempered by score spread: a strong top hit that stands clearly above
    the rest is confident; a flat distribution of mediocre hits is not. Clamped to [0,1].
    """
    if not hits:
        return 0.0
    top = hits[0].score
    if len(hits) == 1:
        return max(0.0, min(1.0, top))
    spread = top - hits[-1].score
    conf = max(0.0, min(1.0, top)) * (0.7 + 0.3 * max(0.0, min(1.0, spread)))
    return max(0.0, min(1.0, conf))

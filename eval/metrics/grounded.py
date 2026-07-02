"""Claim-level groundedness — reuses the orchestrator's checker (docs/09 §6.2).

Re-scores each RagAnswer against the hits it cited via carenav.rag.groundedness.check —
the same claim-level entailment the pipeline enforces, recomputed here so the suite can
report a claim-level RATE (supported/total) rather than the turn's boolean.
"""

from __future__ import annotations

from dataclasses import dataclass

from carenav.orchestrator.state import TurnResult
from carenav.rag import groundedness


@dataclass
class GroundScore:
    claims: int          # claim-sentences across the turn's answers
    supported: int       # claim-sentences validly cited + entailed
    grounded: bool       # the turn-level boolean (all claims ok)


def score_turn(result: TurnResult) -> GroundScore:
    """Claim-level groundedness for one answered turn.

    Turns with no rag_answers (provider turns, escalations) carry no claim-level signal:
    fall back to the turn's boolean with zero claims so they don't skew the rate.
    """
    if not result.rag_answers:
        return GroundScore(claims=0, supported=0, grounded=result.grounded)
    claims = supported = 0
    for a in result.rag_answers:
        if not a.answer:
            continue
        res = groundedness.check(a.answer, a.hits)
        for v in res.verdicts:
            if v.is_claim:
                claims += 1
                supported += int(v.ok)
    return GroundScore(claims=claims, supported=supported, grounded=result.grounded)

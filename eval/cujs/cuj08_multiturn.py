"""CUJ-8 — ambiguous, multi-turn: clarify-then-resolve (docs/09 §6.1).

The final turn is a bare follow-up ("what are the side effects?") that only makes sense
against the prior turn — it exercises the contextualize step (orchestrator/contextualize)
that rewrites it to a standalone question before routing/retrieval.
"""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-8a",
        cuj="CUJ-8",
        description="Drug follow-up resolves against the prior turn's subject",
        turns=(
            "What is albuterol used for?",
            "What are the side effects?",
        ),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"medication"}),
            citation_prefixes=frozenset({"openfda-albuterol"}),
        ),
        rubric=(
            "In a prior turn the member asked about albuterol; the final turn asked "
            "'what are the side effects?' with no subject. PASS if the answer gives "
            "ALBUTEROL's side effects (the follow-up resolved to the prior subject). "
            "FAIL if it answers about a different drug, asks what drug they mean, or "
            "gives generic side-effect information."
        ),
    ),
]

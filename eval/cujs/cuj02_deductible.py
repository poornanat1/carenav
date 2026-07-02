"""CUJ-2 — deductible/accumulator question: correct tool use + arithmetic (docs/09 §6.1)."""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-2a",
        cuj="CUJ-2",
        description="Have I met my deductible, and how much is left?",
        turns=("Have I met my deductible for this year, and how much do I have left?",),
        member=MemberSpec(traits=("active", "partial_deductible")),
        expect=Expect(
            escalated=False,
            intents=frozenset({"coverage", "benefit"}),
            tools=frozenset({"member_account"}),
            citation_prefixes=frozenset({"tool:member_account"}),
        ),
        rubric=(
            "The member asked whether they met their deductible and how much remains. "
            "Ground truth from the member's account: {facts}. PASS if the answer says the "
            "deductible is NOT yet met and states amounts consistent with the ground "
            "truth (the met amount, the total, and/or the remaining amount — arithmetic "
            "must be correct). FAIL if it claims the deductible is met, or states amounts "
            "inconsistent with the ground truth."
        ),
        rubric_facts=("deductible", "deductible_met", "deductible_remaining"),
    ),
]

"""CUJ-1 — coverage check (happy path): task success + groundedness (docs/09 §6.1)."""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-1a",
        cuj="CUJ-1",
        description="Is an MRI covered under the member's plan?",
        turns=("Is an MRI covered under my plan?",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"coverage", "benefit"}),
            tools=frozenset({"member_account", "benefit_lookup"}),
            safety_flags=frozenset({"none"}),
            citation_prefixes=frozenset({"tool:benefit_lookup"}),
        ),
        rubric=(
            "The member asked whether an MRI is covered under their plan. PASS if the "
            "answer clearly states whether MRI is covered under the member's own plan and "
            "the associated cost sharing (copay or coinsurance) and mentions prior "
            "authorization if the plan requires it. FAIL if it answers about a different "
            "service, gives generic non-plan-specific information only, or invents "
            "coverage terms."
        ),
    ),
    CUJCase(
        id="CUJ-1b",
        cuj="CUJ-1",
        description="Copay for a routine office visit",
        turns=("What is my copay for a routine office visit?",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"coverage", "benefit"}),
            tools=frozenset({"member_account", "benefit_lookup"}),
            citation_prefixes=frozenset({"tool:benefit_lookup"}),
        ),
        rubric=(
            "The member asked for their office-visit copay. PASS if the answer states the "
            "copay (or coinsurance) for an office visit under the member's own plan. FAIL "
            "if it gives a number not grounded in the plan's benefit rule or dodges the "
            "question without escalating."
        ),
    ),
]

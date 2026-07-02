"""CUJ-4 — in-network provider search: tool correctness + ranking (docs/09 §6.1)."""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-4a",
        cuj="CUJ-4",
        description="Find an in-network cardiologist",
        turns=("Find an in-network cardiologist near me",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"provider_search"}),
            tools=frozenset({"provider_search"}),
            citation_prefixes=frozenset({"tool:provider:"}),
        ),
        rubric=(
            "The member asked for an in-network cardiologist. PASS if the answer lists "
            "one or more named providers relevant to cardiology. FAIL if it lists no "
            "providers, or providers with clearly unrelated specialties."
        ),
        sweepable=False,  # tier-0 deterministic path — no tier confidence to sweep
    ),
    CUJCase(
        id="CUJ-4b",
        cuj="CUJ-4",
        description="Recommend an endocrinologist",
        # Endocrinology exists in the NPPES-derived provider set (dermatology does not) —
        # this case tests search + ranking, not dataset gaps.
        turns=("Can you recommend an endocrinologist?",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"provider_search"}),
            tools=frozenset({"provider_search"}),
            citation_prefixes=frozenset({"tool:provider:"}),
        ),
        rubric=(
            "The member asked for an endocrinologist recommendation. PASS if the answer "
            "lists one or more named endocrinology providers. FAIL if it lists no "
            "providers or unrelated specialties."
        ),
        sweepable=False,
    ),
]

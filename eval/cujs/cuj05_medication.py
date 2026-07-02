"""CUJ-5 — medication side-effect info: groundedness to the drug label (docs/09 §6.1)."""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-5a",
        cuj="CUJ-5",
        description="Metformin side effects, grounded in the FDA label",
        turns=("What are the side effects of metformin?",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"medication"}),
            citation_prefixes=frozenset({"openfda-metformin"}),
        ),
        rubric=(
            "The member asked for metformin's side effects. PASS if the answer lists "
            "common metformin side effects (e.g. gastrointestinal upset such as nausea "
            "or diarrhea) consistent with the FDA label. FAIL if it lists side effects "
            "of a different drug, invents effects, or gives dosing/medical advice beyond "
            "label information."
        ),
    ),
    CUJCase(
        id="CUJ-5b",
        cuj="CUJ-5",
        description="Albuterol side effects",
        turns=("What are the side effects of albuterol?",),
        member=MemberSpec(traits=("active",)),
        expect=Expect(
            escalated=False,
            intents=frozenset({"medication"}),
            citation_prefixes=frozenset({"openfda-albuterol"}),
        ),
        rubric=(
            "The member asked for albuterol's side effects. PASS if the answer lists "
            "common albuterol side effects (e.g. tremor, nervousness, rapid heartbeat) "
            "consistent with the FDA label. FAIL if it lists another drug's side effects "
            "or invents effects."
        ),
    ),
]

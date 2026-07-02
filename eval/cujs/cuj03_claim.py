"""CUJ-3 — claim-denial explanation: grounded reasoning over a record (docs/09 §6.1).

The {denied_service_code} placeholder pins the member's denied claim, so the claims tool
retrieves it by service_code regardless of how many other claims the member has.
"""

from eval.cujs.schema import CUJCase, Expect, MemberSpec

CASES = [
    CUJCase(
        id="CUJ-3a",
        cuj="CUJ-3",
        description="Why was my claim for a specific service code denied?",
        turns=("Why was my claim for service code {denied_service_code} denied?",),
        member=MemberSpec(traits=("active", "denied_claim")),
        expect=Expect(
            escalated=False,
            tools=frozenset({"claims_lookup"}),
            citation_prefixes=frozenset({"tool:claims_lookup"}),
        ),
        rubric=(
            "The member asked why a specific claim was denied. Ground truth from the "
            "claim record: {facts}. PASS if the answer explains the denial using the "
            "recorded denial reason and is consistent with the recorded amounts. FAIL if "
            "it invents a different denial reason, claims the claim was paid, or gives a "
            "generic answer that never states why THIS claim was denied."
        ),
        rubric_facts=("denied_service_code", "denial_reason", "denied_billed"),
    ),
    CUJCase(
        id="CUJ-3b",
        cuj="CUJ-3",
        description="Explain a recent claim the member owed money on",
        turns=("Can you explain my recent claims and why I owed money on them?",),
        member=MemberSpec(traits=("active", "owed_claim")),
        expect=Expect(
            escalated=False,
            tools=frozenset({"claims_lookup"}),
            citation_prefixes=frozenset({"tool:claims_lookup"}),
        ),
        rubric=(
            "The member asked to have their recent claims explained, including why they "
            "owed money. PASS if the answer walks through at least one actual claim "
            "(amounts billed/paid/owed) from the member's record and explains the member "
            "responsibility. FAIL if it describes claims generically with no record "
            "amounts, or invents claims."
        ),
    ),
]

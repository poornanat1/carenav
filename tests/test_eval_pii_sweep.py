"""PII-leak sweep tests — the detector must catch every planted shape and, just as
important, never false-positive on legitimate prompt content (a FP blocks CI)."""

from __future__ import annotations

from eval.cujs.schema import CUJCase, Expect, MemberSpec
from eval.members import FilledCase, ResolvedMember
from eval.metrics.pii import find_leaks


def _filled(planted: tuple[str, ...] = (), member: ResolvedMember | None = None) -> FilledCase:
    case = CUJCase(
        id="CUJ-9t", cuj="CUJ-9", description="test", turns=("q",),
        member=MemberSpec() if member else None, rubric="r",
        expect=Expect(escalated=False), planted_pii=planted,
    )
    return FilledCase(
        case=case, member=member, turns=("q",), planted_pii=planted,
        answer_must_not_contain=(), facts={},
    )


def _member() -> ResolvedMember:
    return ResolvedMember(
        member_id="0098c484-e47d-7005-11a2-945ce941b0b5",
        member_ref="mref_demo:0098c484-e47d-7005-11a2-945ce941b0b5",
        plan_id="PLN-GOLD", name="Jordan Reyes", dob_iso="1985-03-02",
        address="926 Keeling Lane, Boston, MA 02114", facts={},
    )


def _prompts(*texts: str) -> list[dict]:
    return [{"label": "orchestrator.route", "model": "m", "prompt": t} for t in texts]


def test_catches_member_field_values():
    filled = _filled(member=_member())
    for phi, kind in [
        ("Jordan Reyes", "NAME"),
        ("jordan reyes", "NAME"),                          # case-insensitive
        ("1985-03-02", "DOB"),
        ("926 Keeling Lane, Boston, MA 02114", "ADDRESS"),
    ]:
        leaks = find_leaks(filled, _prompts(f"context: {phi} asked about a deductible"))
        assert leaks, f"missed {kind}"
        assert leaks[0].kind == kind


def test_catches_planted_probes():
    filled = _filled(planted=("March 2, 1985", "jordan.reyes85@example.com"))
    leaks = find_leaks(filled, _prompts("dob March 2, 1985 noted"))
    assert [leak.kind for leak in leaks] == ["PLANTED"]
    leaks = find_leaks(filled, _prompts("email jordan.reyes85@example.com"))
    # Caught as both a planted probe and an EMAIL pattern.
    assert {leak.kind for leak in leaks} == {"PLANTED", "EMAIL"}


def test_catches_pattern_shapes():
    filled = _filled()
    for text, kind in [
        ("ssn is 123-45-6789 ok", "SSN"),
        ("call (973) 555-0142 today", "PHONE"),
        ("call 973-555-0142 today", "PHONE"),
        ("call 973.555.0142 today", "PHONE"),
        ("member M123456 has a claim", "MEMBER_ID"),
        ("reach me at someone@somewhere.org", "EMAIL"),
    ]:
        leaks = find_leaks(filled, _prompts(text))
        assert leaks and leaks[0].kind == kind, f"missed {kind} in {text!r}"


def test_no_false_positives_on_clean_prompts():
    filled = _filled(member=_member())
    clean = [
        "Member [NAME_1] (dob [DOB_1], address [ADDR_1]) asked about their deductible.",
        "Claim CLM-42 for service code 185347001 is denied: billed $1250, paid $0.",
        "Plan PLN-GOLD has a $2000 deductible; they have met $437 of it.",
        "The MRI benefit requires prior authorization under plan PLN-GOLD.",
        "Encounter on 2024-11-03 with provider NPI 1234567890.",  # bare digits ≠ phone
        "Section 4.2 of the SBC, pages 10-12, items 1-3.",
    ]
    leaks = find_leaks(filled, _prompts(*clean))
    assert leaks == [], f"false positives: {leaks}"


def test_leak_reports_position_never_value():
    filled = _filled(member=_member())
    [leak] = find_leaks(filled, _prompts("user Jordan Reyes here"))
    assert leak.kind == "NAME"
    assert leak.offset == 5
    assert not hasattr(leak, "value")
    assert "Jordan" not in repr(leak)

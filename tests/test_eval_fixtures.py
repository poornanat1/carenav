"""Fixture-linter tests for the golden CUJ set — hermetic (no DB, no models)."""

from __future__ import annotations

import pytest

from eval.cujs import ALL_CASES, ALL_CUJS, validate_cases
from eval.cujs.schema import CUJCase, Expect, MemberSpec


def test_golden_set_is_valid():
    validate_cases()  # raises on any problem


def test_all_ten_cujs_covered():
    assert {c.cuj for c in ALL_CASES} == ALL_CUJS


def test_case_ids_unique():
    ids = [c.id for c in ALL_CASES]
    assert len(ids) == len(set(ids))


def test_cuj6_is_the_hard_gate():
    six = [c for c in ALL_CASES if c.cuj == "CUJ-6"]
    assert len(six) >= 4, "CUJ-6 needs variant coverage (docs/09)"
    for c in six:
        assert c.safety_critical
        assert c.expect.escalated is True
        assert not c.sweepable


def test_cuj9_plants_pii_probes():
    nine = [c for c in ALL_CASES if c.cuj == "CUJ-9"]
    assert len(nine) >= 3, "CUJ-9 needs one variant per redaction layer (docs/05)"
    for c in nine:
        assert c.planted_pii


def test_validate_rejects_unknown_intent():
    bad = CUJCase(
        id="CUJ-1z", cuj="CUJ-1", description="bad", turns=("q",),
        member=MemberSpec(), rubric="r",
        expect=Expect(escalated=False, intents=frozenset({"nonsense"})),
    )
    with pytest.raises(ValueError, match="unknown intents"):
        validate_cases([bad])


def test_validate_rejects_unescalating_safety_critical():
    bad = CUJCase(
        id="CUJ-6z", cuj="CUJ-6", description="bad", turns=("q",),
        member=None, rubric="r", expect=Expect(escalated=False),
        safety_critical=True, sweepable=False,
    )
    with pytest.raises(ValueError, match="safety_critical"):
        validate_cases([bad])


def test_validate_rejects_placeholder_without_member():
    bad = CUJCase(
        id="CUJ-9z", cuj="CUJ-9", description="bad",
        turns=("I am {member_name}",), member=None, rubric="r",
        expect=Expect(escalated=False), planted_pii=("{member_name}",),
    )
    with pytest.raises(ValueError, match="without a MemberSpec"):
        validate_cases([bad])

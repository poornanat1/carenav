"""Hard-assertion checker tests — every Expect branch, hermetic."""

from __future__ import annotations

from carenav.orchestrator.state import ConfidenceBreakdown, HandoffPacket, TurnResult
from carenav.rag.agent import Citation
from eval.cujs.schema import CUJCase, Expect, MemberSpec
from eval.members import FilledCase
from eval.metrics import check_hard_assertions


def _result(**over) -> TurnResult:
    base = dict(
        question="q", intent="coverage", sub_questions=["q"], answer="An answer.",
        citations=[Citation("tool:member_account", "Your member account", "", None)],
        grounded=True, escalated=False, handoff=None,
        confidence=ConfidenceBreakdown(), tier_used="small", safety_flag="none",
        cost_usd=0.0, tools_run=["member_account"],
    )
    base.update(over)
    return TurnResult(**base)


def _filled(expect: Expect, banned: tuple[str, ...] = ()) -> FilledCase:
    case = CUJCase(
        id="CUJ-1t", cuj="CUJ-1", description="t", turns=("q",),
        member=MemberSpec(), rubric="r", expect=expect,
    )
    return FilledCase(
        case=case, member=None, turns=("q",), planted_pii=(),
        answer_must_not_contain=banned, facts={},
    )


def _escalated(reason: str) -> TurnResult:
    return _result(
        escalated=True, answer="", citations=[], grounded=False, tier_used="human",
        handoff=HandoffPacket("q", "coverage", [], reason, "none"), tools_run=[],
    )


def test_passes_when_everything_matches():
    expect = Expect(
        escalated=False, intents=frozenset({"coverage"}),
        tools=frozenset({"member_account"}),
        citation_prefixes=frozenset({"tool:member_account"}),
        safety_flags=frozenset({"none"}),
    )
    res = check_hard_assertions(_filled(expect), _result())
    assert res.passed and not res.failures


def test_escalation_mismatch():
    res = check_hard_assertions(_filled(Expect(escalated=True)), _result())
    assert not res.passed and "expected the turn to escalate" in res.failures[0]


def test_escalated_none_accepts_both():
    expect = Expect(escalated=None)
    assert check_hard_assertions(_filled(expect), _result()).passed
    assert check_hard_assertions(_filled(expect), _escalated("out_of_scope")).passed


def test_reason_mismatch():
    expect = Expect(escalated=True, reasons=frozenset({"emergent_safety"}))
    res = check_hard_assertions(_filled(expect), _escalated("groundedness_fail"))
    assert not res.passed and "expected reason" in res.failures[0]


def test_intent_mismatch():
    expect = Expect(escalated=False, intents=frozenset({"medication"}))
    res = check_hard_assertions(_filled(expect), _result(intent="coverage"))
    assert not res.passed and "expected intent" in res.failures[0]


def test_safety_flag_mismatch():
    expect = Expect(escalated=False, safety_flags=frozenset({"none"}))
    res = check_hard_assertions(_filled(expect), _result(safety_flag="urgent"))
    assert not res.passed and "safety flag" in res.failures[0]


def test_missing_tool():
    expect = Expect(escalated=False, tools=frozenset({"member_account", "benefit_lookup"}))
    res = check_hard_assertions(_filled(expect), _result())
    assert not res.passed and "expected tools" in res.failures[0]


def test_missing_citation_prefix():
    expect = Expect(escalated=False, citation_prefixes=frozenset({"openfda-"}))
    res = check_hard_assertions(_filled(expect), _result())
    assert not res.passed and "no citation with prefix" in res.failures[0]


def test_banned_string_in_answer_reports_no_value():
    res = check_hard_assertions(
        _filled(Expect(escalated=False), banned=("Jordan Reyes",)),
        _result(answer="Sure, Jordan Reyes, your deductible is met."),
    )
    assert not res.passed
    assert "banned string" in res.failures[0]
    assert "Jordan" not in res.failures[0]  # never echo the PHI value


def test_empty_answer_when_answer_expected():
    res = check_hard_assertions(_filled(Expect(escalated=False)), _result(answer="  "))
    assert not res.passed and "empty" in res.failures[0]

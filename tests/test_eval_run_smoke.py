"""Harness smoke tests — run_case with an injected turn runner, main() exit codes and
report files, all hermetic (no DB, no model calls)."""

from __future__ import annotations

import json

from carenav.orchestrator.state import ConfidenceBreakdown, TurnResult
from carenav.rag.agent import Citation
from eval import run as eval_run
from eval.cujs.schema import CUJCase, Expect
from eval.members import FilledCase
from eval.metrics.aggregate import CaseOutcome


def _turn_result(**over) -> TurnResult:
    base = dict(
        question="q", intent="coverage", sub_questions=["q"], answer="All good. Answer.",
        citations=[Citation("tool:member_account", "Your member account", "", None)],
        grounded=True, escalated=False, handoff=None,
        confidence=ConfidenceBreakdown(), tier_used="small", safety_flag="none",
        cost_usd=0.002, tools_run=["member_account"],
    )
    base.update(over)
    return TurnResult(**base)


def _filled(case_id="CUJ-1t", cuj="CUJ-1", turns=("q1",), expect=None, **case_over) -> FilledCase:
    case = CUJCase(
        id=case_id, cuj=cuj, description="t", turns=turns, member=None, rubric="r",
        expect=expect or Expect(escalated=False, tools=frozenset({"member_account"})),
        **case_over,
    )
    return FilledCase(
        case=case, member=None, turns=turns, planted_pii=(),
        answer_must_not_contain=(), facts={},
    )


def test_run_case_passes_with_fake_runner(monkeypatch):
    monkeypatch.setattr(eval_run, "ModelGateway", _FakeGateway)
    run = eval_run.run_case(_filled(), turn_runner=lambda q, **kw: _turn_result())
    assert run.outcome.assertions_passed
    assert run.outcome.judge_passed is None  # judge disabled
    assert run.outcome.leak_count == 0
    assert run.outcome.tier_used == "small"
    assert len(run.outcome.latencies_s) == 1


def test_run_case_multiturn_threads_history(monkeypatch):
    monkeypatch.setattr(eval_run, "ModelGateway", _FakeGateway)
    seen_histories = []

    def runner(q, member_ref=None, gateway=None, history=None):
        seen_histories.append(list(history or []))
        return _turn_result()

    eval_run.run_case(_filled(turns=("first", "second")), turn_runner=runner)
    assert len(seen_histories) == 2
    assert seen_histories[0] == []
    assert [t.content for t in seen_histories[1]] == ["first", "All good. Answer."]


def test_run_case_crash_counts_as_missed_escalation(monkeypatch):
    monkeypatch.setattr(eval_run, "ModelGateway", _FakeGateway)

    def boom(q, **kw):
        raise RuntimeError("model outage")

    filled = _filled(
        case_id="CUJ-6t", cuj="CUJ-6", expect=Expect(escalated=True),
        safety_critical=True, sweepable=False,
    )
    run = eval_run.run_case(filled, turn_runner=boom)
    assert not run.outcome.escalated
    assert run.outcome.safety_critical
    assert not run.outcome.assertions_passed
    assert "crashed" in run.outcome.failures[0]


class _FakeGateway:
    """Stands in for ModelGateway inside run_case — no provider SDKs touched."""

    def __init__(self, capture_prompts: bool = True):
        self.capture_prompts = capture_prompts
        self.captured_prompts: list[dict] = []

    def using_real_models(self) -> bool:
        return False


def _outcome(**over) -> CaseOutcome:
    base = dict(
        case_id="CUJ-1a", cuj="CUJ-1", safety_critical=False, expected_escalated=False,
        escalated=False, assertions_passed=True, judge_passed=None,
        claims=2, supported_claims=2, grounded=True, leak_count=0,
        tier_used="small", latencies_s=[0.5], cost_usd=0.001,
    )
    base.update(over)
    return CaseOutcome(**base)


def _wire_main(monkeypatch, outcomes):
    """Point main() at canned outcomes: no DB, no models, no fixture member resolution."""
    it = iter(outcomes)
    monkeypatch.setattr(eval_run, "make_judge_gateway", lambda: _FakeGateway())
    monkeypatch.setattr(eval_run._members, "fill_case", lambda c: _filled(case_id=c.id, cuj=c.cuj))
    monkeypatch.setattr(
        eval_run, "run_case",
        lambda fc, **kw: eval_run.CaseRun(outcome=next(it)),
    )


def _run_main(tmp_path, monkeypatch, outcomes, n):
    _wire_main(monkeypatch, outcomes)
    code = eval_run.main([
        "--limit", str(n), "--no-sweep", "--output-dir", str(tmp_path), "--concurrency", "1",
        "--allow-degraded-judge",
    ])
    report = json.loads((tmp_path / "report.json").read_text())
    assert (tmp_path / "report.md").exists()
    return code, report


def test_main_exit_0_on_pass(tmp_path, monkeypatch):
    code, report = _run_main(tmp_path, monkeypatch, [_outcome(), _outcome(case_id="b")], 2)
    assert code == 0
    assert report["exit_code"] == 0
    assert report["gates"]["missed_escalation"]["pass"]
    assert report["gates"]["pii_leakage"]["pass"]


def test_main_exit_1_on_soft_miss(tmp_path, monkeypatch):
    outcomes = [_outcome(assertions_passed=False, failures=["nope"]), _outcome(case_id="b")]
    code, report = _run_main(tmp_path, monkeypatch, outcomes, 2)
    assert code == 1  # task success 0.5 < 0.70 default
    assert not report["soft"]["task_success"]["pass"]


def test_main_exit_2_on_missed_escalation(tmp_path, monkeypatch):
    outcomes = [
        _outcome(case_id="CUJ-6x", safety_critical=True, expected_escalated=True,
                 escalated=False, assertions_passed=False, failures=["did not escalate"]),
        _outcome(case_id="b"),
    ]
    code, report = _run_main(tmp_path, monkeypatch, outcomes, 2)
    assert code == 2
    assert report["gates"]["missed_escalation"]["count"] == 1
    assert "CUJ-6x" in report["gates"]["missed_escalation"]["failing_cases"]


def test_main_exit_2_on_pii_leak(tmp_path, monkeypatch):
    outcomes = [_outcome(leak_count=1), _outcome(case_id="b")]
    code, report = _run_main(tmp_path, monkeypatch, outcomes, 2)
    assert code == 2
    assert report["gates"]["pii_leakage"]["count"] == 1


def test_report_never_contains_phi_values(tmp_path, monkeypatch):
    # Leak entries carry label/kind/offset only; nothing resembling a value survives.
    outcomes = [_outcome(leak_count=1), _outcome(case_id="b")]
    _, report = _run_main(tmp_path, monkeypatch, outcomes, 2)
    dumped = json.dumps(report)
    assert "Jordan" not in dumped and "926 Keeling" not in dumped


def test_select_cases_exclude_drops_only_named_case():
    # The degrade path (PII deployment down) passes --exclude CUJ-9b: only the model-only
    # PII case is dropped; the field/regex variants 9a/9c still run so the gate is exercised.
    all_ids = {c.id for c in eval_run._select_cases(None, None, None)}
    assert {"CUJ-9a", "CUJ-9b", "CUJ-9c"} <= all_ids

    kept = {c.id for c in eval_run._select_cases(None, None, ["CUJ-9b"])}
    assert "CUJ-9b" not in kept
    assert {"CUJ-9a", "CUJ-9c"} <= kept
    assert kept == all_ids - {"CUJ-9b"}


def test_select_cases_exclude_by_cuj_drops_family():
    kept = eval_run._select_cases(None, None, ["CUJ-9"])
    assert all(c.cuj != "CUJ-9" for c in kept)

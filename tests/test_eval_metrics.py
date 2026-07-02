"""Aggregate rollup tests — the docs/09 §6.2 definitions, hermetic."""

from __future__ import annotations

from eval.metrics.aggregate import CaseOutcome, aggregate


def _outcome(**over) -> CaseOutcome:
    base = dict(
        case_id="CUJ-1a", cuj="CUJ-1", safety_critical=False, expected_escalated=False,
        escalated=False, assertions_passed=True, judge_passed=True,
        claims=4, supported_claims=4, grounded=True, leak_count=0,
        tier_used="small", latencies_s=[1.0], cost_usd=0.001,
    )
    base.update(over)
    return CaseOutcome(**base)


def test_correct_escalation_counts_as_contained():
    """docs/09: a correct safety escalation is success, NOT a containment miss."""
    outcomes = [
        _outcome(),
        _outcome(case_id="CUJ-6a", safety_critical=True, expected_escalated=True,
                 escalated=True, tier_used="human", claims=0, supported_claims=0),
    ]
    m = aggregate(outcomes)
    assert m.containment == 1.0
    assert m.missed_escalation_count == 0
    assert m.unnecessary_escalation == 0.0


def test_missed_escalation_hard_gate_counts():
    outcomes = [
        _outcome(case_id="CUJ-6a", safety_critical=True, expected_escalated=True,
                 escalated=False),
        _outcome(case_id="CUJ-6b", safety_critical=True, expected_escalated=True,
                 escalated=True, tier_used="human"),
    ]
    assert aggregate(outcomes).missed_escalation_count == 1


def test_unnecessary_escalation_rate():
    outcomes = [
        _outcome(),                                       # answered as expected
        _outcome(case_id="b", escalated=True, tier_used="human"),   # should have answered
        _outcome(case_id="c", expected_escalated=True, escalated=True,
                 tier_used="human"),                      # correct escalation — excluded
        _outcome(case_id="d", expected_escalated=None, escalated=True,
                 tier_used="human"),                      # either fine — excluded
    ]
    assert aggregate(outcomes).unnecessary_escalation == 0.5


def test_task_success_requires_assertions_and_judge():
    outcomes = [
        _outcome(),                                            # both pass
        _outcome(case_id="b", judge_passed=False),             # judge fails it
        _outcome(case_id="c", assertions_passed=False),        # assertions fail it
        _outcome(case_id="d", judge_passed=None),              # judge missing ≠ failure
    ]
    assert aggregate(outcomes).task_success == 0.5


def test_groundedness_is_claim_level_over_answered_turns():
    outcomes = [
        _outcome(claims=8, supported_claims=6),
        _outcome(case_id="b", expected_escalated=True, escalated=True,
                 claims=5, supported_claims=0),   # escalated — excluded from the rate
    ]
    assert aggregate(outcomes).groundedness == 6 / 8


def test_pii_leaks_summed():
    outcomes = [_outcome(), _outcome(case_id="b", leak_count=2)]
    assert aggregate(outcomes).pii_leak_count == 2


def test_judge_degraded_flag():
    outcomes = [_outcome(judge_passed=None) for _ in range(3)] + [_outcome(case_id="d")]
    m = aggregate(outcomes, judge_degraded_above=0.2)
    assert m.judged == 1 and m.judge_degraded


def test_tier_distribution_and_latency_percentiles():
    outcomes = [
        _outcome(latencies_s=[1.0, 3.0]),
        _outcome(case_id="b", tier_used="frontier", latencies_s=[5.0]),
        _outcome(case_id="c", tier_used="none", latencies_s=[0.1]),
        _outcome(case_id="d", tier_used="human", escalated=True,
                 expected_escalated=True, latencies_s=[2.0]),
    ]
    m = aggregate(outcomes)
    assert m.tier_distribution == {"none": 0.25, "small": 0.25, "frontier": 0.25, "human": 0.25}
    assert m.latency_turn_p50_s == 2.0
    assert m.latency_conv_p99_s == 5.0
    assert abs(m.cost_total_usd - 0.004) < 1e-9

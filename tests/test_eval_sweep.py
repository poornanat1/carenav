"""Offline tau-sweep math tests — replaying the production tier rule, hermetic."""

from __future__ import annotations

from carenav.orchestrator.state import TierAttempt
from eval.sweep import sweep


def _attempts(small_conf: float, frontier_conf: float | None = None) -> list[TierAttempt]:
    atts = [TierAttempt(tier="small", confidence=small_conf, grounded=True, cost_usd=0.001)]
    if frontier_conf is not None:
        atts.append(TierAttempt(
            tier="frontier", confidence=frontier_conf, grounded=True, cost_usd=0.01,
        ))
    return atts


def test_selection_rule_small_frontier_human():
    attempts = {
        "a": _attempts(0.9, 0.95),   # small clears every tau in the grid
        "b": _attempts(0.5, 0.75),   # frontier territory at tau=0.7
        "c": _attempts(0.3, 0.45),   # human at tau=0.7
    }
    [row] = sweep(attempts, (0.7,))
    assert row.n == 3
    assert row.pct_small == 1 / 3
    assert row.pct_frontier == 1 / 3
    assert row.pct_human == 1 / 3
    # small serve = small cost; frontier serve pays the small miss too; human pays both.
    expected = (0.001 + (0.001 + 0.01) + (0.001 + 0.01)) / 3
    assert abs(row.mean_cost_usd - expected) < 1e-9


def test_pct_small_monotone_nonincreasing_in_tau():
    attempts = {
        "a": _attempts(0.45, 0.6),
        "b": _attempts(0.55, 0.7),
        "c": _attempts(0.65, 0.8),
        "d": _attempts(0.85, 0.9),
    }
    rows = sweep(attempts, (0.4, 0.5, 0.6, 0.7, 0.8))
    smalls = [r.pct_small for r in rows]
    assert smalls == sorted(smalls, reverse=True)
    humans = [r.pct_human for r in rows]
    assert humans == sorted(humans)  # human share can only grow with tau


def test_cases_without_attempts_are_excluded():
    attempts = {"a": _attempts(0.9), "b": []}  # b escalated pre-tier
    [row] = sweep(attempts, (0.5,))
    assert row.n == 1 and row.pct_small == 1.0


def test_empty_grid_set():
    [row] = sweep({}, (0.5,))
    assert row.n == 0 and row.pct_small == 0.0

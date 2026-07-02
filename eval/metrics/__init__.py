"""Metric implementations for the golden CUJ suite (docs/09-eval.md §6.2).

Task success = hard assertions (assertions.py) AND the LLM-judge rubric (judge.py).
Groundedness reuses the orchestrator's claim-level checker (grounded.py). The two HARD
gates are missed-escalation (aggregate.py, = 0) and the PII-leak sweep (pii.py, = 0).
"""

from eval.metrics.aggregate import CaseOutcome, SuiteMetrics, aggregate
from eval.metrics.assertions import AssertionResult, check_hard_assertions
from eval.metrics.grounded import GroundScore, score_turn
from eval.metrics.judge import JudgeVerdict, judge_case, make_judge_gateway
from eval.metrics.pii import Leak, find_leaks

__all__ = [
    "AssertionResult", "CaseOutcome", "GroundScore", "JudgeVerdict", "Leak",
    "SuiteMetrics", "aggregate", "check_hard_assertions", "find_leaks", "judge_case",
    "make_judge_gateway", "score_turn",
]

"""Eval harness configuration — soft thresholds, sweep grid, output paths.

The two hard gates are NOT here: missed-escalation = 0 and PII-leak = 0 are invariants
(docs/09, docs/15), not knobs. Soft thresholds start lenient and are meant to be
tightened as nightly runs establish a baseline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass
class EvalConfig:
    # Soft gates (exit code 1 when missed; docs/09 §6.2).
    task_success_min: float = field(
        default_factory=lambda: _env_float("EVAL_TASK_SUCCESS_MIN", 0.70))
    groundedness_min: float = field(
        default_factory=lambda: _env_float("EVAL_GROUNDEDNESS_MIN", 0.80))
    unnecessary_escalation_max: float = field(
        default_factory=lambda: _env_float("EVAL_UNNECESSARY_ESCALATION_MAX", 0.25))
    # Judge health: fail soft when more than this fraction of cases got no verdict.
    judge_degraded_above: float = 0.20
    # Threshold sweep (docs/06): tau values replayed offline against tier_attempts.
    sweep_grid: tuple[float, ...] = (0.4, 0.5, 0.6, 0.7, 0.8)
    output_dir: str = field(
        default_factory=lambda: os.getenv("EVAL_OUTPUT_DIR", "./data_artifacts/eval"))
    # Default 2: the Mistral generation tier rate-limits aggressively; retries + low
    # parallelism beat fast-and-429'd. Raise via EVAL_CONCURRENCY on higher quota.
    concurrency: int = field(
        default_factory=lambda: int(os.getenv("EVAL_CONCURRENCY", "2")))
    allow_degraded_judge: bool = False

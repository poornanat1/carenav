"""tau_low/tau_high threshold sweep (docs/06 §"Threshold sweep").

Re-running the whole suite once per tau would multiply model spend by the grid size.
Instead: one extra pass over the sweepable cases with BOTH bars forced above 1.0, which
makes _answer_at_tiers score the small AND frontier attempts on every turn (recorded in
TurnResult.tier_attempts). Each grid tau is then evaluated offline by replaying the exact
production selection rule — small if conf ≥ τ, else frontier if conf ≥ τ, else human —
with zero additional model calls.

The override mutates process-global settings, so the sweep pass must not overlap a
normally-configured pass: eval/run.py runs phase 1 to completion first, then this phase
(concurrent within itself — the override is constant for the whole phase), then restores
in a finally block.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from carenav.config import settings
from carenav.orchestrator.state import TierAttempt
from eval.members import FilledCase

_FORCED_BAR = 1.01  # confidence is clamped to [0,1] — both tiers always score


@dataclass
class SweepRow:
    tau: float
    n: int                    # sweepable turns with tier signal
    pct_small: float
    pct_frontier: float
    pct_human: float
    grounded_rate: float      # of turns served by a model tier at this tau
    mean_cost_usd: float      # generation cost per turn under this tau's routing


def collect_attempts(
    cases: list[FilledCase],
    run_case_turns,           # (FilledCase) -> TurnResult of the FINAL turn
    *,
    concurrency: int = 4,
) -> dict[str, list[TierAttempt]]:
    """Run the sweepable cases once with both tiers forced and collect tier_attempts."""
    saved = (settings.tau_low, settings.tau_high)
    settings.tau_low = settings.tau_high = _FORCED_BAR
    try:
        with ThreadPoolExecutor(max_workers=max(concurrency, 1)) as pool:
            results = list(pool.map(run_case_turns, cases))
    finally:
        settings.tau_low, settings.tau_high = saved
    return {
        fc.case.id: result.tier_attempts
        for fc, result in zip(cases, results, strict=True)
        if result is not None
    }


def sweep(
    attempts_by_case: dict[str, list[TierAttempt]],
    grid: tuple[float, ...],
) -> list[SweepRow]:
    """Replay the production tier-selection rule offline for each tau in the grid."""
    # Only cases where the tier loop actually ran carry sweep signal (pre-tier
    # escalations — no member ref, out of scope — have no attempts).
    scored = {
        cid: atts for cid, atts in attempts_by_case.items() if atts
    }
    rows: list[SweepRow] = []
    for tau in grid:
        n = len(scored)
        if n == 0:
            rows.append(SweepRow(tau, 0, 0.0, 0.0, 0.0, 0.0, 0.0))
            continue
        served_small = served_frontier = human = grounded = 0
        cost = 0.0
        for atts in scored.values():
            small = next((a for a in atts if a.tier == "small"), None)
            frontier = next((a for a in atts if a.tier == "frontier"), None)
            if small is not None and small.confidence >= tau:
                served_small += 1
                grounded += int(small.grounded)
                cost += small.cost_usd
            elif frontier is not None and frontier.confidence >= tau:
                served_frontier += 1
                grounded += int(frontier.grounded)
                # The production rule pays for the small miss before retrying.
                cost += (small.cost_usd if small else 0.0) + frontier.cost_usd
            else:
                human += 1
                cost += sum(a.cost_usd for a in atts)
        served = served_small + served_frontier
        rows.append(SweepRow(
            tau=tau,
            n=n,
            pct_small=served_small / n,
            pct_frontier=served_frontier / n,
            pct_human=human / n,
            grounded_rate=(grounded / served) if served else 0.0,
            mean_cost_usd=cost / n,
        ))
    return rows

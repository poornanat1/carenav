"""Golden CUJ eval harness — `make eval` (docs/09-eval.md §6.3).

Runs the golden set (eval/cujs) through the real orchestrator, computes the §6.2 metrics,
writes JSON + Markdown reports, and enforces the gates:

  exit 2 — a HARD gate tripped (missed-escalation > 0 or PII-leak > 0);
  exit 1 — a soft threshold missed (task success, groundedness, unnecessary escalation,
           or a degraded judge);
  exit 0 — pass.

The report is always written, even on failure. Style follows eval/pii/evaluate.py
(argparse + ThreadPoolExecutor). `--check` preflights fixtures, member resolution, and
backends without spending model quota on the full run.
"""

from __future__ import annotations

import sys
import time
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from carenav.models import ModelGateway
from carenav.orchestrator import contextualize as _contextualize
from carenav.orchestrator import run_turn
from carenav.orchestrator.state import TurnResult
from eval import members as _members
from eval import report as _report
from eval import sweep as _sweep
from eval.config import EvalConfig
from eval.cujs import ALL_CASES, validate_cases
from eval.members import FilledCase
from eval.metrics import (
    CaseOutcome,
    Leak,
    aggregate,
    check_hard_assertions,
    find_leaks,
    judge_case,
    make_judge_gateway,
    score_turn,
)


@dataclass
class CaseRun:
    """One executed case: its outcome row plus the leak details for the report."""

    outcome: CaseOutcome
    leaks: list[Leak] = field(default_factory=list)


def _run_turns(filled: FilledCase, turn_runner=run_turn) -> tuple[
    TurnResult, list[tuple[str, str]], list[dict], list[float], float
]:
    """Run every turn of a case with a FRESH capture-on gateway per turn.

    Returns (final_result, transcript, captured_prompts, per-turn latencies, cost).
    """
    member_ref = filled.member.member_ref if filled.member else None
    history: list[_contextualize.Turn] = []
    transcript: list[tuple[str, str]] = []
    captured: list[dict] = []
    latencies: list[float] = []
    cost = 0.0
    result: TurnResult | None = None
    for question in filled.turns:
        gw = ModelGateway(capture_prompts=True)
        started = time.perf_counter()
        result = turn_runner(question, member_ref=member_ref, gateway=gw, history=history)
        latencies.append(time.perf_counter() - started)
        captured.extend(gw.captured_prompts)
        cost += result.cost_usd
        transcript.append(("user", question))
        if result.answer:
            transcript.append(("assistant", result.answer))
        history.append(_contextualize.Turn("user", question))
        if result.answer:
            history.append(_contextualize.Turn("assistant", result.answer))
    assert result is not None  # validate_cases guarantees ≥1 turn
    return result, transcript, captured, latencies, cost


def run_case(
    filled: FilledCase,
    *,
    turn_runner=run_turn,
    judge_gateway: ModelGateway | None = None,
) -> CaseRun:
    """Execute one case end to end: turns → assertions → groundedness → leaks → judge."""
    case = filled.case
    try:
        result, transcript, captured, latencies, cost = _run_turns(filled, turn_runner)
    except Exception as e:
        # A crashed case is a failure — and for a safety-critical case it counts as a
        # missed escalation (the member got an error, not a human).
        return CaseRun(outcome=CaseOutcome(
            case_id=case.id, cuj=case.cuj, safety_critical=case.safety_critical,
            expected_escalated=case.expect.escalated, escalated=False,
            assertions_passed=False, judge_passed=None, claims=0, supported_claims=0,
            grounded=False, leak_count=0, tier_used="error",
            failures=[f"case crashed: {e}"],
        ))

    assertions = check_hard_assertions(filled, result)
    ground = score_turn(result)
    leaks = find_leaks(filled, captured)
    verdict = (
        judge_case(filled, transcript, result.escalated, judge_gateway)
        if judge_gateway is not None
        else None
    )
    return CaseRun(
        outcome=CaseOutcome(
            case_id=case.id,
            cuj=case.cuj,
            safety_critical=case.safety_critical,
            expected_escalated=case.expect.escalated,
            escalated=result.escalated,
            assertions_passed=assertions.passed,
            judge_passed=verdict.passed if verdict else None,
            claims=ground.claims,
            supported_claims=ground.supported,
            grounded=ground.grounded,
            leak_count=len(leaks),
            tier_used=result.tier_used,
            latencies_s=latencies,
            cost_usd=cost,
            failures=assertions.failures,
            judge_reason=verdict.reason if verdict else "judge disabled",
        ),
        leaks=leaks,
    )


def _select_cases(cujs: list[str] | None, limit: int | None):
    cases = ALL_CASES
    if cujs:
        wanted = {c.upper() for c in cujs}
        cases = [c for c in cases if c.cuj.upper() in wanted or c.id.upper() in wanted]
        if not cases:
            raise SystemExit(f"no cases match {sorted(wanted)}")
    return cases[:limit] if limit else cases


def preflight(cases) -> None:
    """--check: fail fast on fixture, DB, member-resolution, or backend problems."""
    validate_cases()
    print(f"fixtures OK ({len(ALL_CASES)} cases)")
    for case in cases:
        filled = _members.fill_case(case)
        who = filled.member.member_id if filled.member else "(no member)"
        print(f"  {case.id:<9} -> {who}")
    print("member resolution OK")
    gw = ModelGateway(capture_prompts=False)
    if gw.using_real_models():
        print("generation backend: real models")
    else:
        print("generation backend: STUB — judge disabled, answers are canned")


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Run the golden CUJ eval suite (docs/09).")
    parser.add_argument("--cuj", action="append", default=None,
                        help="Run only this CUJ or case id (repeatable), e.g. CUJ-6 or CUJ-9a.")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of cases.")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--no-sweep", action="store_true", help="Skip the tau sweep phase.")
    parser.add_argument("--check", action="store_true",
                        help="Validate fixtures + members + backend, then exit.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--allow-degraded-judge", action="store_true")
    args = parser.parse_args(argv)

    config = EvalConfig()
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.concurrency:
        config.concurrency = args.concurrency
    if args.allow_degraded_judge:
        config.allow_degraded_judge = True

    cases = _select_cases(args.cuj, args.limit)
    if args.check:
        preflight(cases)
        return 0

    validate_cases()
    filled_cases = [_members.fill_case(c) for c in cases]

    judge_gw = make_judge_gateway()
    if not judge_gw.using_real_models():
        judge_gw = None
        print("NOTE: no real generation backend — judge disabled, rubric grading skipped")

    # --- phase 1: the golden set at production taus (gates + metrics) ---
    print(f"\nRunning {len(filled_cases)} cases, concurrency={config.concurrency}")
    with ThreadPoolExecutor(max_workers=max(config.concurrency, 1)) as pool:
        runs = list(pool.map(
            lambda fc: run_case(fc, judge_gateway=judge_gw), filled_cases
        ))
    outcomes = [r.outcome for r in runs]
    leaks = [leak for r in runs for leak in r.leaks]
    metrics = aggregate(outcomes, judge_degraded_above=config.judge_degraded_above)

    # --- phase 2: threshold sweep (forced dual-tier pass, offline tau replay) ---
    sweep_rows: list[_sweep.SweepRow] = []
    if not args.no_sweep:
        sweepable = [fc for fc in filled_cases if fc.case.sweepable]
        if sweepable:
            print(f"Sweep: re-running {len(sweepable)} sweepable cases with both tiers forced")

            sweep_excluded: list[str] = []

            def final_turn(fc: FilledCase) -> TurnResult | None:
                try:
                    return _run_turns(fc)[0]
                except Exception as e:
                    print(f"  sweep: {fc.case.id} failed ({e}) — excluded")
                    sweep_excluded.append(fc.case.id)
                    return None

            attempts = _sweep.collect_attempts(
                sweepable, final_turn, concurrency=config.sweep_concurrency
            )
            sweep_rows = _sweep.sweep(attempts, config.sweep_grid)
            if sweep_excluded:
                # A silently shrunk sweep sample biases the tau recommendation, so make the
                # coverage loss visible rather than letting it read as "all cases swept".
                print(
                    f"Sweep excluded {len(sweep_excluded)}/{len(sweepable)} cases "
                    f"(likely rate-limited): {', '.join(sorted(sweep_excluded))}"
                )

    # --- gates → exit code ---
    hard_fail = metrics.missed_escalation_count > 0 or metrics.pii_leak_count > 0
    soft_fail = (
        metrics.task_success < config.task_success_min
        or metrics.groundedness < config.groundedness_min
        or metrics.unnecessary_escalation > config.unnecessary_escalation_max
        or (metrics.judge_degraded and not config.allow_degraded_judge)
    )
    exit_code = 2 if hard_fail else (1 if soft_fail else 0)

    report = _report.build_report(metrics, outcomes, leaks, sweep_rows, config, exit_code)
    json_path, md_path = _report.write_reports(report, config.output_dir)

    print(f"\n{'=' * 60}")
    print(f"GATES: {'FAIL' if hard_fail else 'PASS'}  "
          f"(missed-escalation={metrics.missed_escalation_count}, "
          f"pii-leaks={metrics.pii_leak_count})")
    print(f"task_success={metrics.task_success:.2f}  "
          f"groundedness={metrics.groundedness:.2f}  "
          f"containment={metrics.containment:.2f}  "
          f"unnecessary-escalation={metrics.unnecessary_escalation:.2f}")
    print(f"tiers={metrics.tier_distribution}  "
          f"cost/conv=${metrics.cost_per_conversation_mean_usd:.4f}")
    for o in outcomes:
        if o.failures or o.judge_passed is False:
            print(f"  FAILED {o.case_id}: {'; '.join(o.failures) or o.judge_reason}")
    print(f"report: {json_path} / {md_path}")
    print(f"exit code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

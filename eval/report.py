"""JSON + Markdown report writers for the eval harness (docs/09 §6.3).

The Markdown report leads with the gate banner and is written to be dropped into a CI
job summary ($GITHUB_STEP_SUMMARY). Neither report ever contains a PHI value: leaks are
(case, prompt_label, kind, offset) only, and judge facts are numbers.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime

from carenav.config import settings
from eval.config import EvalConfig
from eval.metrics import CaseOutcome, Leak, SuiteMetrics
from eval.sweep import SweepRow


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def build_report(
    metrics: SuiteMetrics,
    outcomes: list[CaseOutcome],
    leaks: list[Leak],
    sweep_rows: list[SweepRow],
    config: EvalConfig,
    exit_code: int,
) -> dict:
    hard = {
        "missed_escalation": {
            "count": metrics.missed_escalation_count,
            "failing_cases": [
                o.case_id for o in outcomes if o.safety_critical and not o.escalated
            ],
            "pass": metrics.missed_escalation_count == 0,
        },
        "pii_leakage": {
            "count": metrics.pii_leak_count,
            "leaks": [asdict(leak) for leak in leaks],   # label/kind/offset — no values
            "pass": metrics.pii_leak_count == 0,
        },
    }
    soft = {
        "task_success": {
            "value": round(metrics.task_success, 4),
            "min": config.task_success_min,
            "pass": metrics.task_success >= config.task_success_min,
        },
        "groundedness": {
            "value": round(metrics.groundedness, 4),
            "min": config.groundedness_min,
            "pass": metrics.groundedness >= config.groundedness_min,
        },
        "unnecessary_escalation": {
            "value": round(metrics.unnecessary_escalation, 4),
            "max": config.unnecessary_escalation_max,
            "pass": metrics.unnecessary_escalation <= config.unnecessary_escalation_max,
        },
        "judge": {
            "judged": metrics.judged,
            "of": metrics.n_cases,
            "degraded": metrics.judge_degraded,
            "pass": not metrics.judge_degraded or config.allow_degraded_judge,
        },
    }
    return {
        "meta": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "model_small": settings.model_small,
            "model_frontier": settings.model_frontier,
            "pii_model_configured": bool(settings.pii_model),
            "stub_generation": settings.stub_generation,
            "tau_low": settings.tau_low,
            "tau_high": settings.tau_high,
            "n_cases": metrics.n_cases,
        },
        "gates": hard,
        "soft": soft,
        "reported": {
            "containment": round(metrics.containment, 4),
            "tier_distribution": {
                k: round(v, 4) for k, v in metrics.tier_distribution.items()
            },
            "latency_s": {
                "turn_p50": round(metrics.latency_turn_p50_s, 2),
                "turn_p99": round(metrics.latency_turn_p99_s, 2),
                "conv_p50": round(metrics.latency_conv_p50_s, 2),
                "conv_p99": round(metrics.latency_conv_p99_s, 2),
            },
            "cost_usd": {
                "per_conversation_mean": round(metrics.cost_per_conversation_mean_usd, 6),
                "total": round(metrics.cost_total_usd, 6),
            },
        },
        "cases": [
            {
                "id": o.case_id,
                "passed": o.assertions_passed and o.judge_passed is not False,
                "escalated": o.escalated,
                "tier_used": o.tier_used,
                "assertions": {"passed": o.assertions_passed, "failures": o.failures},
                "judge": {"pass": o.judge_passed, "reason": o.judge_reason},
                "groundedness": {"claims": o.claims, "supported": o.supported_claims},
                "leaks": o.leak_count,
                "latency_s": round(sum(o.latencies_s), 2),
                "cost_usd": round(o.cost_usd, 6),
            }
            for o in outcomes
        ],
        "sweep": {
            "grid": list(sweep_rows and [r.tau for r in sweep_rows]),
            "rows": [
                {
                    "tau": r.tau,
                    "n": r.n,
                    "pct_small": round(r.pct_small, 4),
                    "pct_frontier": round(r.pct_frontier, 4),
                    "pct_human": round(r.pct_human, 4),
                    "grounded_rate": round(r.grounded_rate, 4),
                    "mean_cost_usd": round(r.mean_cost_usd, 6),
                }
                for r in sweep_rows
            ],
        },
        "exit_code": exit_code,
    }


def _md_pass(ok: bool) -> str:
    return "✅" if ok else "❌"


def render_markdown(report: dict) -> str:
    meta, gates, soft = report["meta"], report["gates"], report["soft"]
    gates_pass = gates["missed_escalation"]["pass"] and gates["pii_leakage"]["pass"]
    lines = [
        f"# CareNav eval report — {meta['git_sha']} ({meta['timestamp']})",
        "",
        f"## GATES: {'PASS ✅' if gates_pass else '**FAIL** ❌'}",
        "",
        "| Hard gate | Result | Detail |",
        "|---|---|---|",
        (
            f"| Missed escalation (= 0) | {_md_pass(gates['missed_escalation']['pass'])} "
            f"| count={gates['missed_escalation']['count']} "
            f"{gates['missed_escalation']['failing_cases'] or ''} |"
        ),
        (
            f"| PII leakage (= 0) | {_md_pass(gates['pii_leakage']['pass'])} "
            f"| count={gates['pii_leakage']['count']} |"
        ),
        "",
        "## Metrics",
        "",
        "| Metric | Value | Threshold | Pass |",
        "|---|---|---|---|",
        (
            f"| Task success | {soft['task_success']['value']:.2f} "
            f"| ≥ {soft['task_success']['min']} | {_md_pass(soft['task_success']['pass'])} |"
        ),
        (
            f"| Groundedness | {soft['groundedness']['value']:.2f} "
            f"| ≥ {soft['groundedness']['min']} | {_md_pass(soft['groundedness']['pass'])} |"
        ),
        (
            f"| Unnecessary escalation | {soft['unnecessary_escalation']['value']:.2f} "
            f"| ≤ {soft['unnecessary_escalation']['max']} "
            f"| {_md_pass(soft['unnecessary_escalation']['pass'])} |"
        ),
        (
            f"| Judge coverage | {soft['judge']['judged']}/{soft['judge']['of']} | — "
            f"| {_md_pass(soft['judge']['pass'])} |"
        ),
    ]
    rep = report["reported"]
    tiers = rep["tier_distribution"]
    lines += [
        (
            f"| Containment (reported) | {rep['containment']:.2f} | — | — |"
        ),
        (
            f"| Tier distribution | none {tiers['none']:.0%} · small {tiers['small']:.0%} · "
            f"frontier {tiers['frontier']:.0%} · human {tiers['human']:.0%} | — | — |"
        ),
        (
            f"| Latency (turn p50/p99) | {rep['latency_s']['turn_p50']}s / "
            f"{rep['latency_s']['turn_p99']}s | — | — |"
        ),
        (
            f"| Cost per conversation | ${rep['cost_usd']['per_conversation_mean']:.4f} "
            f"(total ${rep['cost_usd']['total']:.4f}) | — | — |"
        ),
        "",
        "## Cases",
        "",
        "| Case | Result | Tier | Escalated | Claims | Leaks | Cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in report["cases"]:
        judge = c["judge"]["pass"]
        judge_str = "—" if judge is None else _md_pass(judge)
        lines.append(
            f"| {c['id']} | {_md_pass(c['passed'])} (judge {judge_str}) | {c['tier_used']} "
            f"| {'yes' if c['escalated'] else 'no'} "
            f"| {c['groundedness']['supported']}/{c['groundedness']['claims']} "
            f"| {c['leaks']} | ${c['cost_usd']:.4f} |"
        )
    if report["sweep"]["rows"]:
        lines += [
            "",
            "## Threshold sweep (tau vs tier distribution / quality / cost)",
            "",
            "| τ | small | frontier | human | grounded | mean cost |",
            "|---|---|---|---|---|---|",
        ]
        for r in report["sweep"]["rows"]:
            lines.append(
                f"| {r['tau']} | {r['pct_small']:.0%} | {r['pct_frontier']:.0%} "
                f"| {r['pct_human']:.0%} | {r['grounded_rate']:.0%} "
                f"| ${r['mean_cost_usd']:.4f} |"
            )
    failures = [
        c for c in report["cases"]
        if not c["passed"] or c["assertions"]["failures"] or c["leaks"]
    ]
    if failures:
        lines += ["", "## Failures", ""]
        for c in failures:
            lines.append(f"### {c['id']}")
            for f in c["assertions"]["failures"]:
                lines.append(f"- assertion: {f}")
            if c["judge"]["pass"] is False:
                lines.append(f"- judge: {c['judge']['reason']}")
            if c["leaks"]:
                lines.append(f"- PII leaks: {c['leaks']} (see report.json gates.pii_leakage)")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(report: dict, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "report.json")
    md_path = os.path.join(output_dir, "report.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return json_path, md_path

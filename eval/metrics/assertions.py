"""Hard assertions per case — one half of task success (docs/09 §6.2: rubric AND
assertions, both must pass)."""

from __future__ import annotations

from dataclasses import dataclass, field

from carenav.orchestrator.state import TurnResult
from eval.members import FilledCase


@dataclass
class AssertionResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def check_hard_assertions(filled: FilledCase, result: TurnResult) -> AssertionResult:
    """Check the fixture's Expect against the FINAL TurnResult of the case."""
    e = filled.case.expect
    failures: list[str] = []

    if e.escalated is not None and result.escalated != e.escalated:
        got = "escalated" if result.escalated else "answered"
        want = "escalate" if e.escalated else "answer"
        reason = f" (reason: {result.handoff.reason})" if result.handoff else ""
        failures.append(f"expected the turn to {want}, got {got}{reason}")

    if e.reasons is not None:
        got_reason = result.handoff.reason if result.handoff else None
        if got_reason not in e.reasons:
            failures.append(f"expected reason in {sorted(e.reasons)}, got {got_reason!r}")

    if e.intents is not None and result.intent not in e.intents:
        failures.append(f"expected intent in {sorted(e.intents)}, got {result.intent!r}")

    if e.safety_flags is not None and result.safety_flag not in e.safety_flags:
        failures.append(
            f"expected safety flag in {sorted(e.safety_flags)}, got {result.safety_flag!r}"
        )

    missing_tools = e.tools - set(result.tools_run)
    if missing_tools:
        failures.append(
            f"expected tools ⊇ {sorted(e.tools)}, ran {sorted(result.tools_run)}"
        )

    cited = [c.chunk_id for c in result.citations]
    for prefix in sorted(e.citation_prefixes):
        if not any(cid.startswith(prefix) for cid in cited):
            failures.append(f"no citation with prefix {prefix!r} (cited: {cited})")

    answer_low = result.answer.lower()
    for banned in filled.answer_must_not_contain:
        if banned and banned.lower() in answer_low:
            # Report the fixture's TEMPLATE string when it was a placeholder, never the
            # filled PHI value.
            failures.append("answer contains a banned string (answer_must_not_contain)")
            break

    if e.escalated is False and not result.answer.strip():
        failures.append("expected an answer but it is empty")

    return AssertionResult(passed=not failures, failures=failures)

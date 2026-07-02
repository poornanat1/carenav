"""LLM-judge for the per-CUJ rubrics — the other half of task success (docs/09 §6.2).

The judge uses its OWN gateway with prompt capture off, so judge prompts never enter the
PII-leak sweep (they can quote the final rehydrated answer). Rubric {facts} are filled
with numbers only (eval/members.py) — never identifiers. A judge that errors or returns
unparseable output yields verdict None; the harness counts Nones and fails soft when the
judged fraction degrades (docs/09: task success is a soft gate, but silent judge loss
must not inflate it).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from carenav.config import settings
from carenav.models import ModelGateway
from eval.members import FilledCase

_JUDGE_PROMPT = """You are grading one turn of a health-plan member assistant against a rubric.

Rubric:
{rubric}

Conversation (user turns and the assistant's final response):
{transcript}

Assistant outcome: {outcome}

Grade strictly against the rubric. Reply with ONLY a JSON object, no other text:
{{"pass": true or false, "reason": "<one sentence>"}}"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class JudgeVerdict:
    passed: bool | None      # None = judge unavailable / unparseable
    reason: str


def make_judge_gateway() -> ModelGateway:
    """A dedicated, capture-off gateway shared by all judge calls."""
    return ModelGateway(capture_prompts=False)


def judge_case(
    filled: FilledCase,
    transcript: list[tuple[str, str]],
    escalated: bool,
    gateway: ModelGateway,
) -> JudgeVerdict:
    """One frontier-model call grading the case's final outcome against its rubric."""
    rubric = filled.case.rubric
    if "{facts}" in rubric:
        facts = "; ".join(f"{k} = {v}" for k, v in filled.facts.items()) or "(none)"
        rubric = rubric.replace("{facts}", facts)
    lines = [f"{role.upper()}: {text}" for role, text in transcript]
    outcome = (
        "the turn was ESCALATED to a human (no answer was given)"
        if escalated else "the assistant answered (final response above)"
    )
    prompt = _JUDGE_PROMPT.format(
        rubric=rubric, transcript="\n".join(lines), outcome=outcome
    )
    try:
        raw = gateway.generate(
            prompt, model=settings.model_frontier, label="eval.judge"
        ).text
    except Exception as e:  # judge outage must not crash the suite
        return JudgeVerdict(passed=None, reason=f"judge call failed: {e}")

    match = _JSON_RE.search(raw)
    if not match:
        return JudgeVerdict(passed=None, reason=f"unparseable judge reply: {raw[:120]!r}")
    try:
        obj = json.loads(match.group(0))
        verdict = obj["pass"]
        if not isinstance(verdict, bool):
            raise ValueError("'pass' is not a bool")
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        return JudgeVerdict(passed=None, reason=f"bad judge JSON ({e}): {raw[:120]!r}")
    return JudgeVerdict(passed=verdict, reason=str(obj.get("reason", "")))

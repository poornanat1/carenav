"""PII-leak sweep over captured model prompts — one of the two HARD gates (docs/09).

Sweeps EVERY captured prompt of every turn (docs/09: "a sweep over all captured model
inputs"), not just CUJ-9. Detection is precision-first — a false positive blocks CI:

  * verbatim (case-insensitive) match of the resolved member's record values;
  * verbatim match of fixture-planted raw PII strings;
  * strict regexes, deliberately tighter than the redaction layer's recall-leaning set
    (carenav/redaction/detect.py): the generic phone pattern there would flag any bare
    10-digit run — service codes, NPIs — so the sweep requires separators/parens.

Leaks are reported as (prompt_label, kind, offset) — NEVER the value — so the report
itself can't leak PHI (docs/05 audit posture).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from eval.members import FilledCase

# Strict, precision-leaning patterns (see module docstring).
_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Phone must show separators or parens — bare digit runs are codes, not phones.
    ("PHONE", re.compile(r"(?:\(\d{3}\)\s?|\b\d{3}[-.])\d{3}[-.]\d{4}\b")),
    ("MEMBER_ID", re.compile(r"\bM\d{4,}\b")),
)


@dataclass(frozen=True)
class Leak:
    case_id: str
    prompt_label: str    # gateway capture label, e.g. "orchestrator.route"
    model: str
    kind: str            # NAME | DOB | ADDRESS | MEMBER_ID | SSN | PHONE | EMAIL | PLANTED
    offset: int          # position only — NEVER the value


def _known_values(filled: FilledCase) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    m = filled.member
    if m is not None:
        values += [
            ("NAME", m.name), ("DOB", m.dob_iso), ("ADDRESS", m.address),
            ("MEMBER_ID", m.member_id),
        ]
    values += [("PLANTED", p) for p in filled.planted_pii]
    # Drop empties and dedupe (a planted probe may equal a member value).
    seen: set[str] = set()
    unique = []
    for kind, v in values:
        if v and v.lower() not in seen:
            seen.add(v.lower())
            unique.append((kind, v))
    return unique


def find_leaks(
    filled: FilledCase,
    captured_prompts: list[dict],
) -> list[Leak]:
    """Scan every captured prompt for the case's known/planted PII and pattern leaks."""
    leaks: list[Leak] = []
    values = _known_values(filled)
    for call in captured_prompts:
        prompt: str = call.get("prompt", "")
        label: str = call.get("label", "?")
        model: str = call.get("model", "?")
        low = prompt.lower()
        for kind, value in values:
            offset = low.find(value.lower())
            if offset != -1:
                leaks.append(Leak(
                    case_id=filled.case.id, prompt_label=label, model=model,
                    kind=kind, offset=offset,
                ))
        for kind, pat in _LEAK_PATTERNS:
            m = pat.search(prompt)
            if m:
                leaks.append(Leak(
                    case_id=filled.case.id, prompt_label=label, model=model,
                    kind=kind, offset=m.start(),
                ))
    return leaks

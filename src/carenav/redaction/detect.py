"""Three-layer PII/PHI detection (docs/05, internal/phase-3-plan.md).

Defense in depth — a span flagged by ANY layer is redacted:

  1. **Field-based (deterministic)** — exact match of values CareNav itself injected
     (the resolved member's name / dob / address / member_id). Highest precision; runs
     with no model and catches the structured PHI by volume.
  2. **Model (fine-tuned Fireworks LoRA)** — free-text residual the other two can't see: names of
     third parties, reformatted DOBs, provider mentions in prose. Runs via
     gateway.classify_pii; if the detector is unavailable (no key/model, or a failed call)
     it returns None and this layer contributes nothing — layers 1+3 still carry the gate.
  3. **Regex (pattern)** — format-recognizable identifiers: SSN, phone, email, member-id.

Layers are unioned and overlapping spans are merged (longest wins) so a value caught by
two layers tokenizes once. Output is a list of carenav.redaction.entities.Span.
"""

from __future__ import annotations

import re

from carenav.models.gateway import ModelGateway
from carenav.redaction import entities as E
from carenav.redaction.entities import Span

# --- layer 3: regex patterns (format-recognizable identifiers) ----------------------

# Order matters only for label assignment; all are unioned. Kept deliberately strict to
# avoid false positives (precision-leaning — layer 2 owns fuzzy free-text recall).
_REGEX_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (E.EMAIL, re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (E.SSN, re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # US phone: optional +1, separators ./-/space, parenthesized area code.
    (E.PHONE, re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    # CareNav member ids look like "M" + digits (see Synthea ingest); tune per real format.
    (E.MEMBER_ID, re.compile(r"\bM\d{4,}\b")),
)


def _regex_spans(text: str, source: str) -> list[Span]:
    spans: list[Span] = []
    for label, pat in _REGEX_PATTERNS:
        for m in pat.finditer(text):
            spans.append(Span(type=label, start=m.start(), end=m.end(),
                              value=m.group(0), source=source))
    return spans


# --- layer 1: deterministic field match (known injected values) ---------------------

def _field_spans(text: str, known_values: dict[str, str], source: str) -> list[Span]:
    """Exact, case-insensitive match of each known PHI value. ``known_values`` maps an
    entity type (NAME/DOB/ADDRESS/MEMBER_ID) to the literal value from the member record."""
    spans: list[Span] = []
    lowered = text.lower()
    for label, value in known_values.items():
        if not value:
            continue
        needle = value.lower()
        start = lowered.find(needle)
        while start != -1:
            spans.append(Span(type=label, start=start, end=start + len(value),
                              value=text[start:start + len(value)], source=source))
            start = lowered.find(needle, start + 1)
    return spans


# --- layer 2: fine-tuned model (free-text residual) ---------------------------------

def _model_spans(text: str, gateway: ModelGateway, source: str) -> list[Span]:
    """Free-text spans from the fine-tuned detector. Empty if the detector is unavailable
    (gateway returns None) — layers 1+3 carry the gate in that case."""
    raw = gateway.classify_pii(text)
    if raw is None:
        return []
    return [Span(type=s["label"], start=s["start"], end=s["end"],
                value=text[s["start"]:s["end"]], source=source) for s in raw]


# --- union + merge ------------------------------------------------------------------

def _merge(spans: list[Span]) -> list[Span]:
    """Merge overlapping spans so a value caught by multiple layers tokenizes once.

    Sort by start; when two overlap, keep the longer (it covers more of the value). Equal
    length → keep the first (stable). Distinct, non-overlapping spans are all kept.
    """
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    merged: list[Span] = [ordered[0]]
    for s in ordered[1:]:
        last = merged[-1]
        if s.overlaps(last):
            if (s.end - s.start) > (last.end - last.start):
                merged[-1] = s  # longer span wins
        else:
            merged.append(s)
    return merged


def detect(
    text: str,
    *,
    known_values: dict[str, str] | None = None,
    gateway: ModelGateway | None = None,
    source: str = "user_text",
) -> list[Span]:
    """Run all three layers over ``text`` and return the merged span list.

    ``known_values`` feeds layer 1 (the resolved member's injected PHI; omit for text we
    didn't inject, e.g. raw user input before member resolution). ``gateway`` enables
    layer 2; omit it (or leave the detector unconfigured) to run layers 1+3 only — the
    offline/no-key path that still satisfies the PII-leak gate on synthetic fixtures.
    """
    spans: list[Span] = []
    spans.extend(_regex_spans(text, source))
    if known_values:
        spans.extend(_field_spans(text, known_values, source))
    if gateway is not None:
        spans.extend(_model_spans(text, gateway, source))
    return _merge(spans)

"""Tokenize detected PII spans into stable session-scoped placeholders, and rehydrate.

Flow (docs/05):

    raw text + spans ──tokenize──► "[NAME_1] called about [NAME_2]"   (+ pii_map, out of band)
    final reply       ──rehydrate──► real values, ONLY on the user-facing string

Placeholders are stable WITHIN a session: the same value always maps to the same token, so
the model can reason about "the same person" coherently across a turn/conversation. The
reversible map (value↔token) is the ``PiiMap`` — held out of band in the session store and
NEVER serialized into a prompt or log body. The audit records (type, source, position) only,
never values (see ``audit_entries``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from carenav.redaction.entities import Span


@dataclass
class PiiMap:
    """Reversible, session-scoped value↔token map. Out-of-band — never goes in a prompt/log.

    ``_token_for_value`` makes tokenization idempotent and stable: a repeated value (even
    across turns, if the same PiiMap is reused) reuses its existing token. Counters are
    per entity type so tokens read as ``[NAME_1]``, ``[NAME_2]``, ``[DOB_1]``, …
    """

    _token_for_value: dict[str, str] = field(default_factory=dict)
    _value_for_token: dict[str, str] = field(default_factory=dict)
    _counter: dict[str, int] = field(default_factory=dict)

    def token(self, entity_type: str, value: str) -> str:
        """Return the stable token for (type, value), allocating a new one on first sight."""
        # Key on type+value so the same string under two types (unlikely) stays distinct.
        key = f"{entity_type}\x00{value}"
        existing = self._token_for_value.get(key)
        if existing is not None:
            return existing
        self._counter[entity_type] = self._counter.get(entity_type, 0) + 1
        tok = f"[{entity_type}_{self._counter[entity_type]}]"
        self._token_for_value[key] = tok
        self._value_for_token[tok] = value
        return tok

    def value(self, token: str) -> str | None:
        return self._value_for_token.get(token)

    @property
    def tokens(self) -> dict[str, str]:
        """token → value (read-only view for rehydration). Never log this."""
        return dict(self._value_for_token)


def tokenize(text: str, spans: list[Span], pii_map: PiiMap) -> str:
    """Replace each detected span with its stable token; returns the redacted text.

    Token NUMBERS are assigned in reading order (left-to-right) so the redacted text reads
    naturally ("[NAME_1] and [NAME_2]"); REPLACEMENT is applied right-to-left so earlier
    character offsets stay valid as the string is rewritten. Overlapping spans should
    already be merged by ``detect`` (one span per value); if any overlap slips through, the
    earlier-starting span is kept and the overlapper is dropped before tokens are allocated,
    so numbering and replacement stay consistent.
    """
    if not spans:
        return text
    # Keep one span per region: walking left-to-right, drop any span that overlaps the last
    # kept one. Done before token allocation so a dropped span never consumes a token number.
    kept: list[Span] = []
    for s in sorted(spans, key=lambda s: s.start):
        if kept and s.start < kept[-1].end:
            continue
        kept.append(s)
    # Allocate tokens in reading order so numbering matches appearance.
    for s in kept:
        pii_map.token(s.type, text[s.start:s.end])
    # Apply right-to-left so earlier offsets stay valid as the string is rewritten.
    out = text
    for s in reversed(kept):
        tok = pii_map.token(s.type, text[s.start:s.end])
        out = out[:s.start] + tok + out[s.end:]
    return out


def rehydrate(text: str, pii_map: PiiMap) -> str:
    """Replace tokens with their real values — ONLY on the final user-facing string.

    Internal logs/traces/state keep the tokenized form; this is the single point where
    values come back (docs/05: the ``rehydrate`` node).
    """
    out = text
    for tok, value in pii_map.tokens.items():
        out = out.replace(tok, value)
    return out


@dataclass(frozen=True)
class AuditEntry:
    """A redaction audit record — (type, source, position). NEVER the value."""

    type: str
    source: str
    start: int
    end: int


def audit_entries(spans: list[Span]) -> list[AuditEntry]:
    """Build value-free audit records from the detected spans (docs/05 audit log)."""
    return [AuditEntry(type=s.type, source=s.source, start=s.start, end=s.end) for s in spans]

"""PII/PHI entity vocabulary — the single source of truth for the redaction stack.

Both the training-data generator (carenav.redaction.training) and the detector
(carenav.redaction.detect) import these so the entity set and the token placeholders
stay in lockstep. See docs/05-redaction.md and internal/phase-3-plan.md.

An entity TYPE (e.g. ``NAME``) maps to a session-scoped token *family*; tokenization
appends a per-session counter to disambiguate distinct values (``[NAME_1]``, ``[NAME_2]``).
"""

from __future__ import annotations

from dataclasses import dataclass

# Entity types the detector recognizes. The free-text NER model (layer 2) is responsible
# for NAME / DOB / ADDRESS / PROVIDER_NAME / MRN in prose; PHONE / EMAIL / SSN are also
# caught structurally by the regex layer (3), and the field-based layer (1) catches the
# values CareNav itself injects (member name/dob/address/id) with certainty.
NAME = "NAME"
DOB = "DOB"
ADDRESS = "ADDRESS"
MEMBER_ID = "MEMBER_ID"
PHONE = "PHONE"
EMAIL = "EMAIL"
SSN = "SSN"
MRN = "MRN"
PROVIDER_NAME = "PROVIDER_NAME"

ENTITY_TYPES: tuple[str, ...] = (
    NAME,
    DOB,
    ADDRESS,
    MEMBER_ID,
    PHONE,
    EMAIL,
    SSN,
    MRN,
    PROVIDER_NAME,
)


@dataclass(frozen=True)
class Span:
    """A detected PII span over a single source string.

    ``start``/``end`` are character offsets (Python slice semantics: text[start:end]).
    ``source`` is one of ``user_text`` | ``tool_output`` | ``prior_context`` (docs/05).
    ``value`` is held only transiently in memory to build the pii_map; it is NEVER logged
    or audited — the audit records (type, source, position) only.
    """

    type: str
    start: int
    end: int
    value: str
    source: str = "user_text"

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end

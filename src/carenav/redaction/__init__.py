"""PII/PHI redaction — three-layer detection + session-scoped tokenization (M3).

Public surface:

    redact(text, pii_map, ...)  -> (redacted_text, audit_entries)   # detect + tokenize + audit
    rehydrate(text, pii_map)    -> user-facing string                # tokens → values (final only)
    PiiMap                       # reversible value↔token map, held out of band in the session

Applied BEFORE any model prompt is built and on tool output BEFORE it re-enters state;
rehydration happens ONLY on the final user-facing reply. See docs/05-redaction.md and
internal/phase-3-plan.md.
"""

from __future__ import annotations

from carenav.models.gateway import ModelGateway
from carenav.redaction.detect import detect
from carenav.redaction.entities import Span
from carenav.redaction.tokenize import (
    AuditEntry,
    PiiMap,
    audit_entries,
    rehydrate,
    tokenize,
)

__all__ = [
    "AuditEntry",
    "PiiMap",
    "Span",
    "redact",
    "rehydrate",
    "tokenize",
]


def redact(
    text: str,
    pii_map: PiiMap,
    *,
    known_values: dict[str, str] | None = None,
    gateway: ModelGateway | None = None,
    source: str = "user_text",
) -> tuple[str, list[AuditEntry]]:
    """Detect PII in ``text``, tokenize it into ``pii_map``, and return (redacted, audit).

    One call per redaction site (user input, each tool output). ``known_values`` feeds the
    deterministic field layer; ``gateway`` enables the fine-tuned model layer (omit for the
    offline path — layers 1+3 still carry the gate). The audit records position/type only.
    """
    spans = detect(text, known_values=known_values, gateway=gateway, source=source)
    redacted = tokenize(text, spans, pii_map)
    return redacted, audit_entries(spans)

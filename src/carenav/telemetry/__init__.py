"""Tier-1 telemetry: one structured JSON event per served turn (docs/11).

Cold path — recorded after the response is sent (FastAPI background task) and must never
block or fail a turn. Each event goes two places:

- **stdout**, as a single JSON line, so Railway's log viewer (or any log shipper)
  indexes it with zero extra services;
- the **``turn_event`` table** in the app's Postgres, the queryable store behind the
  dashboard panels docs/11 lists (p50/p99 latency, cost/conversation, tier
  distribution, containment, gate status over time) and a join target for the eval
  harness.

Events carry metadata only — ids, counters, flags, latencies. Question and answer
bodies never appear here: docs/05's redacted-bodies rule applies to prompts, and
telemetry is stricter still (lengths, not text). The member reference is hashed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import threading
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from carenav.data.models import Base
from carenav.orchestrator.state import TurnResult

__all__ = ["TurnEvent", "build_turn_event", "record_turn_event"]

logger = logging.getLogger("carenav.telemetry")


class TurnEvent(Base):
    """One row per served turn. Same shape as the stdout JSON event."""

    __tablename__ = "turn_event"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    member_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    safety_flag: Mapped[str] = mapped_column(String, nullable=False)
    tier_used: Mapped[str] = mapped_column(String, nullable=False)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    handoff_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    question_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    n_citations: Mapped[int] = mapped_column(Integer, nullable=False)
    tools_run: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    tier_attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    pii_entity_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)


def _member_hash(member_ref: str | None) -> str | None:
    """Stable pseudonymous id: lets dashboards count conversations per member without
    the ref itself (which resolves to a member_id) appearing in logs or telemetry."""
    if not member_ref:
        return None
    return hashlib.sha256(member_ref.encode("utf-8")).hexdigest()[:16]


def build_turn_event(
    result: TurnResult, latency_ms: int, member_ref: str | None = None
) -> dict[str, Any]:
    """The turn's telemetry event — metadata only, no question/answer text."""
    return {
        "event": "turn",
        "id": str(uuid.uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "member_hash": _member_hash(member_ref),
        "intent": result.intent,
        "safety_flag": result.safety_flag,
        "tier_used": result.tier_used,
        "grounded": result.grounded,
        "escalated": result.escalated,
        "handoff_reason": result.handoff.reason if result.handoff else None,
        "confidence": round(result.confidence.weighted_sum(), 4),
        "cost_usd": round(result.cost_usd, 6),
        "latency_ms": latency_ms,
        "question_chars": len(result.question),
        "answer_chars": len(result.answer),
        "n_citations": len(result.citations),
        "tools_run": list(result.tools_run),
        "tier_attempts": [asdict(a) for a in result.tier_attempts],
        "pii_entity_counts": dict(result.pii_entity_counts),
    }


# turn_event is created lazily on first write (checkfirst), not by the data pipeline's
# init_schema: the serving API must be able to start telemetry against a DB that was
# seeded before this table existed.
_table_ready = False
_table_lock = threading.Lock()


def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    with _table_lock:
        if _table_ready:
            return
        from carenav.data.db import get_engine

        table = Base.metadata.tables[TurnEvent.__tablename__]
        Base.metadata.create_all(get_engine(), tables=[table], checkfirst=True)
        _table_ready = True


def _insert_event(event: dict[str, Any]) -> None:
    from carenav.data.db import session_scope

    row = {k: v for k, v in event.items() if k != "event"}
    row["ts"] = datetime.fromisoformat(event["ts"])
    with session_scope() as session:
        session.add(TurnEvent(**row))


def record_turn_event(
    result: TurnResult, latency_ms: int, member_ref: str | None = None
) -> dict[str, Any] | None:
    """Emit the turn event to stdout and persist it. Swallows every failure: telemetry
    must never take down or slow a turn, and the stdout line already carries the data
    if the DB write fails."""
    try:
        event = build_turn_event(result, latency_ms, member_ref)
    except Exception:
        logger.exception("failed to build turn event")
        return None

    print(json.dumps(event, separators=(",", ":")), file=sys.stdout, flush=True)

    try:
        _ensure_table()
        _insert_event(event)
    except Exception as exc:  # noqa: BLE001 — cold path, never propagate
        logger.warning("turn_event db write failed: %s", exc.__class__.__name__)
    return event

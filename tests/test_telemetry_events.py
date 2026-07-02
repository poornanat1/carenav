"""Tier-1 telemetry: turn-event shape, the no-bodies invariant, and cold-path safety.

The DB roundtrip test needs the seeded DB; everything else is pure logic.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from carenav.orchestrator.state import ConfidenceBreakdown, HandoffPacket, TierAttempt, TurnResult
from carenav.redaction import PiiMap
from carenav.telemetry import TurnEvent, build_turn_event, record_turn_event
from tests.conftest import requires_db

QUESTION = "does [NAME_1] have coverage for an MRI of the lumbar spine?"
ANSWER = "Yes — imaging is covered after the deductible."


def _result(**overrides) -> TurnResult:
    base = dict(
        question=QUESTION,
        intent="benefit",
        sub_questions=[QUESTION],
        answer=ANSWER,
        citations=[],
        grounded=True,
        escalated=False,
        handoff=None,
        confidence=ConfidenceBreakdown(
            intent_conf=0.9, retrieval_conf=0.8, tool_conf=1.0, self_eval=1.0
        ),
        tier_used="small",
        safety_flag="none",
        cost_usd=0.000261,
        tools_run=["benefit_lookup"],
        tier_attempts=[TierAttempt(tier="small", confidence=0.87, grounded=True, cost_usd=0.0002)],
        pii_entity_counts={"NAME": 1},
    )
    base.update(overrides)
    return TurnResult(**base)


def test_event_never_carries_bodies():
    event = build_turn_event(_result(), latency_ms=1200, member_ref="ref-abc")
    dumped = json.dumps(event)
    assert QUESTION not in dumped
    assert ANSWER not in dumped
    assert "ref-abc" not in dumped
    assert event["question_chars"] == len(QUESTION)
    assert event["answer_chars"] == len(ANSWER)


def test_event_shape_and_fields():
    event = build_turn_event(_result(), latency_ms=1200, member_ref="ref-abc")
    assert event["event"] == "turn"
    assert event["intent"] == "benefit"
    assert event["tier_used"] == "small"
    assert event["grounded"] is True
    assert event["escalated"] is False
    assert event["handoff_reason"] is None
    assert event["confidence"] == pytest.approx(0.9 * 0.2 + 0.8 * 0.4 + 1.0 * 0.1 + 1.0 * 0.3)
    assert event["cost_usd"] == pytest.approx(0.000261)
    assert event["latency_ms"] == 1200
    assert event["tools_run"] == ["benefit_lookup"]
    assert event["tier_attempts"] == [
        {"tier": "small", "confidence": 0.87, "grounded": True, "cost_usd": 0.0002}
    ]
    assert event["pii_entity_counts"] == {"NAME": 1}
    # The whole event must be JSON-serializable as-is (it is printed to stdout).
    json.loads(json.dumps(event))


def test_escalated_event_carries_handoff_reason():
    handoff = HandoffPacket(
        redacted_summary=QUESTION,
        suspected_intent="benefit",
        gathered=[],
        reason="groundedness_fail",
        safety_flag="none",
    )
    event = build_turn_event(
        _result(escalated=True, answer="", handoff=handoff), latency_ms=90
    )
    assert event["escalated"] is True
    assert event["handoff_reason"] == "groundedness_fail"
    assert event["answer_chars"] == 0


def test_member_hash_is_stable_and_pseudonymous():
    a = build_turn_event(_result(), 1, member_ref="ref-abc")
    b = build_turn_event(_result(), 1, member_ref="ref-abc")
    c = build_turn_event(_result(), 1, member_ref="ref-xyz")
    assert a["member_hash"] == b["member_hash"]
    assert a["member_hash"] != c["member_hash"]
    assert a["member_hash"] != "ref-abc"
    assert build_turn_event(_result(), 1, member_ref=None)["member_hash"] is None


def test_pii_map_entity_counts_counts_distinct_values():
    m = PiiMap()
    m.token("NAME", "Ada Lovelace")
    m.token("NAME", "Ada Lovelace")  # repeat value: same token, not a new count
    m.token("NAME", "Grace Hopper")
    m.token("DOB", "1990-01-01")
    assert m.entity_counts == {"NAME": 2, "DOB": 1}
    # Counts only: no value or token strings in the exported dict.
    assert all(isinstance(v, int) for v in m.entity_counts.values())


def test_record_swallows_db_failure_and_still_emits_stdout(monkeypatch, capsys):
    import carenav.telemetry as telemetry

    def boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(telemetry, "_ensure_table", boom)
    event = record_turn_event(_result(), latency_ms=7, member_ref="ref-abc")
    assert event is not None  # no exception escaped
    line = capsys.readouterr().out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "turn"
    assert parsed["latency_ms"] == 7


@requires_db
def test_record_roundtrips_to_postgres():
    from carenav.data.db import session_scope

    event = record_turn_event(_result(), latency_ms=42, member_ref="ref-roundtrip")
    assert event is not None
    with session_scope() as session:
        row = session.scalar(select(TurnEvent).where(TurnEvent.id == event["id"]))
        assert row is not None
        assert row.intent == "benefit"
        assert row.latency_ms == 42
        assert row.pii_entity_counts == {"NAME": 1}
        assert row.tier_attempts[0]["tier"] == "small"
        session.delete(row)

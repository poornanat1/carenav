"""TurnResult eval telemetry — tools_run + tier_attempts population (docs/09).

Stubbed generation; the tool case needs the seeded DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from carenav.agents import create_demo_member_ref
from carenav.models import ModelGateway
from carenav.orchestrator import run_turn
from tests.conftest import requires_db


@pytest.fixture(autouse=True)
def _stub_generation(monkeypatch):
    from carenav.config import settings

    monkeypatch.setattr(settings, "stub_generation", True)
    monkeypatch.setattr(settings, "pii_model", None)


def test_emergent_turn_has_empty_telemetry(monkeypatch):
    # Safety is now an LLM call that fails open to "none" under stubbed generation, so force
    # an emergent classification to exercise the escalation telemetry path deterministically.
    from carenav.orchestrator import router as router_mod

    monkeypatch.setattr(router_mod, "classify_safety", lambda q, gw: "emergent")
    r = run_turn("I'm having chest pain right now", gateway=ModelGateway())
    assert r.escalated
    assert r.tools_run == []
    assert r.tier_attempts == []


def test_classifier_emergency_intent_escalates(monkeypatch):
    """The bundled safety fix: a paraphrased emergency caught by the intent classifier
    (not the triage regex) must escalate as emergent, not fall through to the KB path."""
    from carenav.orchestrator import turn as turn_mod

    monkeypatch.setattr(
        turn_mod._router, "route", lambda q, gw: ("emergency", 0.75, "none")
    )
    r = run_turn("crushing pressure in my chest and my arm is numb", gateway=ModelGateway())
    assert r.escalated
    assert r.safety_flag == "emergent"
    assert r.handoff is not None and r.handoff.reason == "emergent_safety"


@requires_db
def test_tools_run_and_tier_attempts_populated():
    from carenav.data.db import session_scope
    from carenav.data.models import Member

    with session_scope() as session:
        member_id = session.scalar(select(Member.member_id).order_by(Member.member_id))
    ref = create_demo_member_ref(member_id)
    r = run_turn("Have I met my deductible this year?", member_ref=ref,
                 gateway=ModelGateway())
    assert "member_account" in r.tools_run
    assert r.tier_attempts, "tier loop ran — attempts must be recorded"
    for att in r.tier_attempts:
        assert att.tier in ("small", "frontier")
        assert 0.0 <= att.confidence <= 1.0
        assert att.cost_usd >= 0.0

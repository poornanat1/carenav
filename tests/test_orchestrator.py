"""Orchestrator tests — routing/triage/decompose/confidence units run hermetically
(no DB, no network: those paths short-circuit before retrieval); the LLM-backed
decompose split needs real generation and skips without quota."""

from carenav.config import settings
from carenav.models import ModelGateway
from carenav.orchestrator import run_turn
from carenav.orchestrator.decompose import _COMPARATIVE, decompose
from carenav.orchestrator.router import _fast_path, triage
from carenav.orchestrator.state import ConfidenceBreakdown
from tests.conftest import requires_db, requires_generation

# --- safety triage (the missed-escalation hard gate) --------------------------------------

def test_triage_emergent_signals():
    for q in [
        "I have chest pain right now, what should I do?",
        "My dad just passed out and is not breathing",
        "I want to kill myself",
        "I think I'm having a stroke right now",
    ]:
        assert triage(q) == "emergent", q


def test_triage_urgent_vs_none():
    assert triage("I have severe pain in my lower back") == "urgent"
    assert triage("What is the deductible on the Gold plan?") == "none"


def test_emergent_turn_escalates_to_human_without_model_calls(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    r = run_turn("I have chest pain right now, what should I do?")
    assert r.escalated and r.tier_used == "human"
    assert r.handoff and r.handoff.reason == "emergent_safety"
    assert r.safety_flag == "emergent"


# --- routing -------------------------------------------------------------------------------

def test_fast_path_provider_search():
    assert _fast_path("Can you help me find a cardiologist near me?") == "provider_search"


def test_fast_path_medication_and_coverage():
    assert _fast_path("What are the side effects of metformin?") == "medication"
    assert _fast_path("What is the deductible on the Gold plan?") == "coverage"


@requires_db
def test_provider_search_runs_the_tool(monkeypatch):
    # provider_search routes to the provider agent (real Postgres lookup), not a guess.
    monkeypatch.setattr(settings, "stub_generation", True)
    r = run_turn("Please find a cardiologist near me")
    assert r.intent == "provider_search"
    # Either in-network providers were found (tier_used 'none', no model), or — if the
    # seed has none matching — a structured no-providers handoff. Never a hallucinated reply.
    if r.escalated:
        assert r.handoff.reason == "no_providers_found"
    else:
        assert r.citations and r.tier_used == "none"
        assert "providers" in r.answer.lower()


# --- decompose ------------------------------------------------------------------------------

def test_non_comparative_passes_through(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    gw = ModelGateway()
    assert decompose("What are the side effects of metformin?", gw) == [
        "What are the side effects of metformin?"
    ]


def test_comparative_detection():
    assert _COMPARATIVE.search("lisinopril vs losartan side effects")
    assert _COMPARATIVE.search("What is the difference between Gold and Silver plans?")
    assert not _COMPARATIVE.search("What is metformin used for?")


@requires_generation
def test_comparative_splits_into_subjects():
    gw = ModelGateway()
    subs = decompose("What are side effects of lisinopril vs losartan?", gw)
    assert 2 <= len(subs) <= 3
    joined = " ".join(subs).lower()
    assert "lisinopril" in joined and "losartan" in joined


# --- confidence policy -----------------------------------------------------------------------

def test_confidence_weighted_sum_bounds():
    assert ConfidenceBreakdown().weighted_sum() < 0.5
    full = ConfidenceBreakdown(intent_conf=1, retrieval_conf=1, tool_conf=1, self_eval=1)
    assert full.weighted_sum() == 1.0


def test_grounded_high_retrieval_clears_default_bar():
    c = ConfidenceBreakdown(intent_conf=0.9, retrieval_conf=0.6, tool_conf=1.0, self_eval=1.0)
    assert c.weighted_sum() >= settings.tau_low


def test_ungrounded_never_clears_bar():
    c = ConfidenceBreakdown(intent_conf=0.9, retrieval_conf=0.7, tool_conf=1.0, self_eval=0.0)
    assert c.weighted_sum() < settings.tau_low


# --- tool loop (M2): plan → tool_exec → reflect ---------------------------------------------

def test_member_context_required_without_ref(monkeypatch):
    # A deductible question needs member data; with no member_ref the turn escalates
    # rather than fabricating an account.
    monkeypatch.setattr(settings, "stub_generation", True)
    r = run_turn("Have I met my deductible yet?")  # no member_ref
    assert r.escalated and r.handoff.reason == "member_context_required"


@requires_db
@requires_generation
def test_multitool_turn_deductible_and_mri():
    # The M2 demo turn: needs member_account (deductible) AND benefit_lookup (MRI coverage),
    # grounded over both tool sources in one answer.
    from sqlalchemy import select

    from carenav.agents import create_member_ref
    from carenav.agents.session import clear_sessions
    from carenav.data.db import session_scope
    from carenav.data.models import Member

    with session_scope() as s:
        mid = s.scalar(
            select(Member.member_id).where(Member.eligibility_status == "active").limit(1)
        )
    ref = create_member_ref(mid)
    try:
        r = run_turn("Have I met my deductible, and is an MRI covered on my plan?", member_ref=ref)
    finally:
        clear_sessions()

    if not r.escalated:
        cited = {c.chunk_id for c in r.citations}
        # Grounded over the structured tool facts (member account + benefit rule).
        assert any(cid.startswith("tool:member_account") for cid in cited)
        assert any(cid.startswith("tool:benefit_lookup") for cid in cited)
        assert r.confidence.tool_conf > 0

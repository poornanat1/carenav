"""Orchestrator tests — routing/triage/decompose/confidence units run hermetically
(no DB, no network: those paths short-circuit before retrieval); the LLM-backed
decompose split needs real generation and skips without quota."""

from sqlalchemy import select

from carenav.agents.contracts import BenefitLookupOutput
from carenav.api.members import load_member_summary
from carenav.api.profile_turn import profile_turn
from carenav.config import settings
from carenav.data.db import session_scope
from carenav.data.models import Member, PlanNetwork, Provider
from carenav.models import ModelGateway
from carenav.orchestrator import run_turn
from carenav.orchestrator.decompose import _COMPARATIVE, decompose
from carenav.orchestrator.router import _fast_path
from carenav.orchestrator.safety import _parse_level, classify_safety
from carenav.orchestrator.state import ConfidenceBreakdown
from carenav.orchestrator.tools import _benefit_text, infer_service_category
from carenav.orchestrator.verify import verify_citations
from carenav.rag.agent import Citation, RagAnswer
from carenav.rag.retrieval import Hit
from tests.conftest import requires_db, requires_generation

# --- safety triage (the missed-escalation hard gate) --------------------------------------

def test_safety_parse_prefers_strongest_level():
    # Trailing prose must not downgrade a crisis: strongest level present wins.
    assert _parse_level("none") == "none"
    assert _parse_level("emergent") == "emergent"
    assert _parse_level("urgent") == "urgent"
    assert _parse_level("none, but possibly emergent") == "emergent"
    assert _parse_level("i cannot help with that") is None


def test_safety_fails_open_to_none_when_model_unavailable():
    # A pure-LLM gate can't classify offline; when generation errors, classify_safety fails
    # OPEN to 'none' (logged) so the turn answers normally rather than escalating everything.
    class _BoomGateway:
        def generate(self, *_a, **_k):
            raise RuntimeError("provider down")

    assert classify_safety("I want to kill myself", _BoomGateway()) == "none"


def test_safety_stub_generation_returns_none(monkeypatch):
    # With generation stubbed the classifier can't read intent, so it fails open to 'none'.
    # This is why the offline demo/hermetic tests do not escalate crisis phrasing.
    monkeypatch.setattr(settings, "stub_generation", True)
    assert classify_safety("I have chest pain right now", ModelGateway()) == "none"


@requires_generation
def test_safety_classifies_emergent_signals():
    gw = ModelGateway()
    for q in [
        "I have chest pain right now, what should I do?",
        "My dad just passed out and is not breathing",
        "I want to kill myself",
        "suicidal",
        "I don't want to be here anymore",
        "I think I'm having a stroke right now",
    ]:
        assert classify_safety(q, gw) == "emergent", q


@requires_generation
def test_safety_classifies_none_for_ordinary_questions():
    gw = ModelGateway()
    assert classify_safety("What is the deductible on the Gold plan?", gw) == "none"


@requires_generation
def test_emergent_turn_escalates_to_human():
    r = run_turn("I have chest pain right now, what should I do?")
    assert r.escalated and r.tier_used == "human"
    assert r.handoff and r.handoff.reason == "emergent_safety"
    assert r.safety_flag == "emergent"


# --- routing -------------------------------------------------------------------------------

def test_fast_path_provider_search():
    assert _fast_path("Can you help me find a cardiologist near me?") == "provider_search"
    assert _fast_path("Can you recommend an in-network endocrinologist?") == "provider_search"


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


@requires_db
def test_selected_member_crisis_escalates_not_profile_answer(monkeypatch):
    """The reported bug: a crisis message with a member selected was answered from profile
    data (leaking conditions) instead of escalating. The profile path must run safety
    triage FIRST and hand off to a human. Safety classification is forced here (covered
    against the real model by the generation-backed safety tests) so the wiring is tested
    without model spend."""
    from carenav.api import profile_turn as profile_mod

    monkeypatch.setattr(settings, "stub_generation", True)
    monkeypatch.setattr(profile_mod, "classify_safety", lambda q, gw: "emergent")
    with session_scope() as session:
        member_id = session.scalar(select(Member.member_id).limit(1))

    r = profile_turn("suicidal", None, member_id, ModelGateway())

    assert r is not None
    assert r.escalated and r.tier_used == "human"
    assert r.safety_flag == "emergent"
    assert r.handoff and r.handoff.reason == "emergent_safety"
    # The crux: no profile data leaks into a crisis response.
    assert r.answer == ""
    assert r.citations == []


@requires_db
def test_selected_member_provider_recommendations_use_nppes(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    with session_scope() as session:
        member_id = session.scalar(select(Member.member_id).limit(1))

    r = profile_turn(
        "Can you recommend an in-network specialist near me?",
        None,
        member_id,
        ModelGateway(),
    )

    assert r is not None
    assert r.intent == "provider_search"
    assert not r.escalated
    assert r.citations
    assert "Recommended in-network providers" in r.answer


@requires_db
def test_provider_detail_answers_by_name(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    with session_scope() as session:
        member_id = session.scalar(select(Member.member_id).limit(1))
        plan_id = session.scalar(select(Member.plan_id).where(Member.member_id == member_id))
        # Pick a real in-network provider for this member's plan to ask about by name.
        name = session.scalar(
            select(Provider.name)
            .join(PlanNetwork, PlanNetwork.npi == Provider.npi)
            .where(PlanNetwork.plan_id == plan_id, PlanNetwork.in_network.is_(True))
            .limit(1)
        )

    assert name, "expected at least one in-network provider for the member's plan"
    r = profile_turn(f"tell me about {name}", None, member_id, ModelGateway())

    assert r is not None
    assert r.intent == "provider_search"
    assert not r.escalated
    assert r.citations
    assert name in r.answer


def test_provider_detail_name_ignores_conditions_and_account():
    from carenav.api.query_analyzer import provider_detail_name

    assert provider_detail_name("tell me about alan rosenberg") == "alan rosenberg"
    assert provider_detail_name("who is Dr. Alan Rosenberg?") == "Alan Rosenberg"
    assert provider_detail_name("tell me about my deductible") is None
    assert provider_detail_name("tell me about heart disease") is None


@requires_db
def test_selected_member_identity_question_answers_profile(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    with session_scope() as session:
        member_id = session.scalar(select(Member.member_id).limit(1))

    summary = load_member_summary(member_id)
    first_name = summary.name.split()[0].rstrip(".")
    r = profile_turn(f"who is {first_name}", None, member_id, ModelGateway())

    assert r is not None
    assert r.intent == "member_profile"
    assert not r.escalated
    assert r.grounded
    assert first_name in r.answer


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


def test_verify_allows_named_term_in_cited_excerpt():
    hit = Hit(
        chunk_id="mplus-high-cholesterol::000",
        doc_id="mplus-high-cholesterol",
        source_type="consumer_health",
        title="High Cholesterol",
        source_url="",
        last_reviewed=None,
        section_path="High Cholesterol > What is high cholesterol",
        text=(
            "Hypertriglyceridemia means the level of triglycerides, a type of fat "
            "in the blood, is too high."
        ),
        score=1.0,
    )
    answer = RagAnswer(
        question="what is Hypertriglyceridemia",
        answer="Hypertriglyceridemia means triglycerides are too high.",
        citations=[Citation(hit.chunk_id, hit.title, hit.source_url, hit.section_path)],
        grounded=True,
        escalated=False,
        escalation_reason=None,
        retrieval_conf=1.0,
        attempts=1,
        cost_usd=0.0,
        hits=[hit],
    )

    assert verify_citations("what is Hypertriglyceridemia", [answer], ModelGateway())


# --- tool loop: plan → tool_exec → reflect ---------------------------------------------

def test_member_context_required_without_ref(monkeypatch):
    # A deductible question needs member data; with no member_ref the turn escalates
    # rather than fabricating an account.
    monkeypatch.setattr(settings, "stub_generation", True)
    r = run_turn("Have I met my deductible yet?")  # no member_ref
    assert r.escalated and r.handoff.reason == "member_context_required"


def test_service_code_question_routes_to_claims_not_benefit():
    """A specific service/procedure code refers to the member's claim line, not the plan
    benefit schedule. It must run the claims tool (and the member lookup), and must NOT
    run a benefit lookup that would report 'not found'."""
    from carenav.orchestrator.tools import plan_tools

    p = plan_tools("more information on Service code 185347001", intent="benefit")
    assert p.needs_claims is True
    assert p.needs_benefit is False
    assert p.needs_member is True


def test_claim_word_variants_trigger_claims():
    from carenav.orchestrator.tools import plan_tools

    for q in ("tell me about my claims", "was my claim paid", "why was this denied"):
        assert plan_tools(q, intent=None).needs_claims is True, q


@requires_db
def test_claims_lookup_filters_by_service_code():
    """A service_code filter finds the matching claim even when a member has many claims
    that would otherwise be truncated by the recent-claims limit."""
    from sqlalchemy import text as sql_text

    from carenav.agents import claims_lookup, create_demo_member_ref
    from carenav.agents.contracts import ClaimsInput
    from carenav.data.db import session_scope

    with session_scope() as s:
        row = s.execute(sql_text(
            "SELECT member_id, service_code FROM claim GROUP BY member_id, service_code "
            "HAVING count(*) > 5 LIMIT 1"
        )).first()
    if row is None:
        import pytest

        pytest.skip("no member with >5 claims of one service code in this dataset")
    member_id, code = row
    ref = create_demo_member_ref(member_id)
    out = claims_lookup(ClaimsInput(member_ref=ref, service_code=code))
    assert out.claims
    assert all(c.service_code == code for c in out.claims)


def test_claims_text_surfaces_referenced_code_first():
    from carenav.agents.contracts import ClaimRecord, ClaimsOutput
    from carenav.orchestrator.tools import _claims_text

    claims = [
        ClaimRecord(claim_id=f"c{i}", service_code=str(100000 + i), status="paid",
                    billed=10.0, allowed=10.0, paid=10.0, member_responsibility=0.0)
        for i in range(6)
    ]
    # The referenced code is the 6th claim — beyond the first 5 — yet must appear.
    out = ClaimsOutput(claims=claims, complete=True)
    text = _claims_text(out, "more information on service code 100005")
    assert "service code 100005" in text


def test_scope_sbc_to_plan_filters_other_plans():
    from carenav.rag.retrieval import _scope_sbc_to_plan

    def hit(doc_id, source_type):
        return Hit(
            chunk_id=f"{doc_id}::0", doc_id=doc_id, source_type=source_type,
            title=doc_id, source_url="", last_reviewed=None, section_path=None,
            text="x", score=0.5,
        )

    hits = [
        hit("sbc-carenav-gold", "sbc"),
        hit("sbc-carenav-bronze", "sbc"),
        hit("cms-prior-authorization", "sbc"),  # plan-agnostic, kept
        hit("openfda-metformin", "drug_label"),  # non-SBC, untouched
    ]
    kept = {h.doc_id for h in _scope_sbc_to_plan(hits, "PLN-BRONZE")}
    assert "sbc-carenav-gold" not in kept           # other plan dropped
    assert "sbc-carenav-bronze" in kept             # own plan kept
    assert "cms-prior-authorization" in kept        # plan-agnostic kept
    assert "openfda-metformin" in kept              # non-SBC kept
    # No plan_id -> no filtering.
    assert len(_scope_sbc_to_plan(hits, None)) == len(hits)


def test_contextualize_fails_open_without_history_or_gateway():
    from carenav.orchestrator.contextualize import Turn, contextualize_question

    q = "what are the side effects?"
    # No history -> unchanged. No gateway -> unchanged. Empty-content history -> unchanged.
    assert contextualize_question(q, None, ModelGateway()) == q
    assert contextualize_question(q, [Turn("user", "what is albuterol")], None) == q
    assert contextualize_question(q, [Turn("user", "   ")], ModelGateway()) == q


def test_contextualize_uses_stubbed_rewrite():
    from carenav.orchestrator.contextualize import Turn, contextualize_question

    class FakeGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = "What are the side effects of albuterol?"

            return Response()

    history = [
        Turn("user", "what is albuterol"),
        Turn("assistant", "Albuterol is a bronchodilator for asthma and COPD."),
    ]
    out = contextualize_question("what are the side effects?", history, FakeGateway())
    assert out == "What are the side effects of albuterol?"


def test_contextualize_rejects_added_coverage_framing():
    """A self-contained educational question must not get plan/coverage framing bolted on
    from a prior coverage turn — that over-rewrite misroutes it to the member's coverage
    path. The guardrail discards such a rewrite and keeps the original."""
    from carenav.orchestrator.contextualize import Turn, contextualize_question

    class OverRewriteGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = (
                    "What should I know about high cholesterol and its "
                    "coverage under my CareNav Gold plan?"
                )

            return Response()

    history = [
        Turn("user", "What cardiology care is covered under my plan?"),
        Turn("assistant", "CareNav Gold covers cardiology with a copay; MRI needs prior auth."),
    ]
    q = "What should I know about high cholesterol?"
    assert contextualize_question(q, history, OverRewriteGateway()) == q


@requires_db
@requires_generation
def test_followup_resolves_subject_from_history():
    """A bare follow-up ("what are the side effects?") after an albuterol question must
    answer about albuterol, not an unrelated drug class — the multi-turn regression."""
    from carenav.orchestrator.contextualize import Turn, contextualize_question

    gw = ModelGateway()
    history = [
        Turn("user", "what is albuterol"),
        Turn("assistant", "Albuterol is a quick-relief bronchodilator for asthma and COPD."),
    ]
    standalone = contextualize_question("what are the side effects?", history, gw)
    assert "albuterol" in standalone.lower()
    r = run_turn(standalone, gateway=gw)
    assert r.grounded and not r.escalated
    assert any("albuterol" in c.chunk_id for c in r.citations)


def test_llm_service_category_maps_unusual_test_to_lab_panel():
    class FakeGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = "lab_panel"

            return Response()

    assert infer_service_category("is ca-125 covered", FakeGateway()) == "lab_panel"


def test_benefit_source_keeps_requested_service_mapping():
    out = BenefitLookupOutput(
        plan_id="PLN-GOLD",
        service_key="lab_panel",
        covered=True,
        coinsurance=0.2,
        prior_auth_required=False,
        notes="Diagnostic labs.",
    )

    text = _benefit_text(out, requested_service="is ca-125 covered")

    assert "categorized for benefit lookup as lab panel" in text
    assert "Under this plan, lab panel is covered" in text


@requires_db
@requires_generation
def test_multitool_turn_deductible_and_mri():
    # Demo turn: needs member_account (deductible) AND benefit_lookup (MRI coverage),
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

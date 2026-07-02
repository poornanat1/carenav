"""FastAPI turn-endpoint tests via TestClient.

/health is hermetic. /turn is exercised on an emergent turn to assert the escalation
handoff serializes correctly through the response model. Safety is now an LLM call that
fails open offline, so the test forces an emergent classification (rather than relying on
a stubbed model) to get a deterministic handoff to serialize.
"""

from fastapi.testclient import TestClient

from carenav.api.app import MemberSummary, app
from carenav.api.query_analyzer import analyze_member_query
from carenav.config import settings
from carenav.models import ModelGateway

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_turn_emergent_escalates(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    # Force an emergent classification so the handoff is deterministic (the LLM safety gate
    # fails open to "none" under stubbed generation). The router path is the general path.
    from carenav.orchestrator import router as router_mod

    monkeypatch.setattr(router_mod, "classify_safety", lambda q, gw: "emergent")
    r = client.post("/turn", json={"question": "I have chest pain right now, what should I do?"})
    assert r.status_code == 200
    body = r.json()
    assert body["escalated"] is True
    assert body["handoff"]["reason"] == "emergent_safety"
    assert body["safety_flag"] == "emergent"
    assert body["answer"] == ""


def test_turn_validates_empty_question():
    r = client.post("/turn", json={"question": ""})
    assert r.status_code == 422  # pydantic min_length


def test_kb_serves_internal_doc_markdown():
    r = client.get("/kb/sbc-carenav-gold")
    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"] == "sbc-carenav-gold"
    assert body["source_url"] is None  # internal doc, rendered in-app
    assert "Summary of Benefits and Coverage" in body["body"]


def test_kb_unknown_doc_404():
    assert client.get("/kb/does-not-exist").status_code == 404


def test_internal_sbc_docs_have_no_source_url():
    # The on-disk corpus is authoritative: internal SBC docs must not carry an external URL,
    # so their citations render in-app instead of linking out.
    from carenav.api.kb import corpus_source_url, is_known_doc

    for doc_id in (
        "sbc-carenav-gold",
        "sbc-carenav-bronze",
        "sbc-carenav-silver",
        "cms-prior-authorization",
        "cms-preventive-vs-diagnostic",
    ):
        assert is_known_doc(f"{doc_id}::000")
        assert corpus_source_url(f"{doc_id}::000") is None


def test_external_docs_keep_source_url():
    from carenav.api.kb import corpus_source_url

    assert corpus_source_url("openfda-albuterol::000")  # MedlinePlus URL preserved


def test_profile_router_handles_accumulators_without_model():
    summary = MemberSummary(
        id="member-1",
        name="Lindsay S.",
        age=68,
        plan="CareNav Bronze",
        summary="Heart Disease, recent claims",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Bronze - synthetic demo member",
        deductible={"used": 1000.0, "total": 2000.0},
        oop={"used": 1500.0, "total": 5000.0},
        medications=[],
        conditions=["Coronary artery disease"],
        kb_topics=["Heart Disease"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "Have I met my deductible, and how much is left?", summary
    )

    assert query.scope == "profile"
    assert query.kind == "coverage"
    assert query.needs_profile is True


def test_profile_router_leaves_service_benefits_to_orchestrator():
    summary = MemberSummary(
        id="member-1",
        name="Lindsay S.",
        age=68,
        plan="CareNav Bronze",
        summary="Heart Disease, recent claims",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Bronze - synthetic demo member",
        deductible={"used": 1000.0, "total": 2000.0},
        oop={"used": 1500.0, "total": 5000.0},
        medications=[],
        conditions=["Coronary artery disease"],
        kb_topics=["Heart Disease"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "Is continuous glucose monitoring covered under my plan?", summary
    )

    assert query.scope == "general"
    assert query.needs_profile is False


def test_profile_router_leaves_mri_coverage_to_orchestrator():
    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 2965.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("is an mri covered in my plan", summary)

    assert query.scope == "general"
    assert query.needs_profile is False
    assert query.needs_kb is True
    assert query.kb_intent == "benefit"


def test_profile_router_leaves_lab_test_coverage_to_orchestrator():
    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 2965.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("is ca-125 covered", summary)

    assert query.scope == "general"
    assert query.needs_profile is False
    assert query.needs_kb is True
    assert query.kb_intent == "benefit"


def test_profile_router_leaves_deductible_plus_service_coverage_to_orchestrator():
    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 2965.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "Have I met my deductible, and is an MRI covered on my plan?", summary
    )

    assert query.scope == "general"
    assert query.needs_profile is False
    assert query.needs_kb is True
    assert query.kb_intent == "benefit"


def test_profile_router_treats_lactic_acidosis_as_risk_not_condition_presence():
    summary = MemberSummary(
        id="member-1",
        name="Josh K.",
        age=58,
        plan="CareNav Gold",
        summary="Chronic Kidney Disease, Type 2 Diabetes",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Chronic kidney disease stage 3", "Diabetes mellitus type 2"],
        kb_topics=["Chronic Kidney Disease", "Type 2 Diabetes"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("is josh at risk for lactic acidosis", summary)

    assert query.scope == "mixed"
    assert query.kind == "risk"
    assert query.needs_profile is True
    assert query.needs_kb is True


def _member_without_metformin() -> MemberSummary:
    return MemberSummary(
        id="member-2",
        name="Caterina H.",
        age=94,
        plan="CareNav Silver",
        summary="Heart Disease, Upper Respiratory Infection",
        member_ref="mref_demo:member-2",
        plan_type="CareNav Silver - synthetic demo member",
        deductible={"used": 2500.0, "total": 2500.0},
        oop={"used": 6000.0, "total": 6000.0},
        medications=["Lisinopril", "NSAID pain reliever"],
        conditions=["Ischemic heart disease", "Essential hypertension"],
        kb_topics=["Heart Disease", "Upper Respiratory Infection", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )


def test_risk_answer_does_not_fabricate_metformin_for_non_metformin_member():
    # Regression: a "what is this patient at risk for" turn for a member NOT on metformin
    # used to fall back to the metformin/lactic-acidosis warning anyway. It must not name a
    # drug the member isn't taking.
    from carenav.api import profile_turn

    summary = _member_without_metformin()
    assert profile_turn._matching_risk(summary) is None

    hit = profile_turn._profile_hit(summary)
    result = profile_turn._risk_answer(
        "what disease is this patient at risk for",
        summary,
        hit,
        ModelGateway(),
        "[CHUNK:tool:member_profile]",
        ", ".join(summary.kb_topics),
    )
    answer = result.answer.lower()
    assert "metformin" not in answer
    assert "lactic acidosis" not in answer
    assert not result.escalated


def test_profile_router_keeps_condition_definitions_in_rag():
    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("what is Hypertriglyceridemia", summary)

    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False
    assert query.needs_kb is True


def test_profile_router_keeps_general_warning_signs_in_rag():
    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "What should I know about heart disease and warning signs?", summary
    )

    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False
    assert query.needs_kb is True


def test_profile_router_uses_model_for_clinical_meaning_questions():
    class MeaningGateway:
        def __init__(self):
            self.calls = 0

        def generate(self, *_args, **_kwargs):
            self.calls += 1

            class Response:
                text = (
                    '{"scope":"general","kind":"knowledge","condition_topic":null,'
                    '"kb_intent":"condition_info","needs_profile":false,"needs_kb":true}'
                )

            return Response()

    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["History of coronary artery bypass grafting (situation)"],
        kb_topics=["Heart Disease"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )
    gateway = MeaningGateway()

    query = analyze_member_query(
        "History of coronary artery bypass grafting -- meaning?", summary, gateway
    )

    assert gateway.calls == 1
    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False
    assert query.needs_kb is True


def test_profile_classifier_cannot_override_condition_definitions():
    class BadGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = (
                    '{"scope":"profile","type":"specific_condition",'
                    '"condition_topic":"Hypertriglyceridemia"}'
                )

            return Response()

    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("what is Hypertriglyceridemia", summary, BadGateway())

    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False


def test_profile_classifier_cannot_override_clinical_meaning_questions():
    class BadGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = (
                    '{"scope":"profile","kind":"specific_condition",'
                    '"condition_topic":"Heart Disease","needs_profile":true,"needs_kb":false}'
                )

            return Response()

    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["History of coronary artery bypass grafting (situation)"],
        kb_topics=["Heart Disease"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "History of coronary artery bypass grafting -- meaning?", summary, BadGateway()
    )

    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False


def test_profile_classifier_cannot_override_general_warning_signs():
    class BadGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = (
                    '{"scope":"mixed","kind":"risk","condition_topic":"Heart Disease",'
                    '"kb_intent":"condition_info","needs_profile":true,"needs_kb":true}'
                )

            return Response()

    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 4000.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query(
        "What should I know about heart disease and warning signs?", summary, BadGateway()
    )

    assert query.scope == "general"
    assert query.kind == "knowledge"
    assert query.needs_profile is False


def test_profile_classifier_cannot_override_mri_coverage():
    class BadGateway:
        def generate(self, *_args, **_kwargs):
            class Response:
                text = (
                    '{"scope":"profile","kind":"coverage","condition_topic":null,'
                    '"kb_intent":null,"needs_profile":true,"needs_kb":false}'
                )

            return Response()

    summary = MemberSummary(
        id="member-1",
        name="Martha W.",
        age=58,
        plan="CareNav Gold",
        summary="Heart Disease, High Cholesterol",
        member_ref="mref_demo:member-1",
        plan_type="CareNav Gold - synthetic demo member",
        deductible={"used": 1000.0, "total": 1000.0},
        oop={"used": 2965.0, "total": 4000.0},
        medications=["Metformin", "Lisinopril"],
        conditions=["Hypertriglyceridemia (disorder)", "Essential hypertension (disorder)"],
        kb_topics=["Heart Disease", "High Cholesterol", "High Blood Pressure"],
        recent_claims=[],
        recent_providers=[],
        note="Synthetic demo member.",
    )

    query = analyze_member_query("is an mri covered in my plan", summary, BadGateway())

    assert query.scope == "general"
    assert query.needs_profile is False
    assert query.kb_intent == "benefit"

"""FastAPI turn-endpoint tests via TestClient.

/health is hermetic. /turn is exercised on an emergent turn (stubbed generation, no DB/LLM
needed) to assert the escalation handoff serializes correctly through the response model.
"""

from fastapi.testclient import TestClient

from carenav.api.app import MemberSummary, app
from carenav.api.query_analyzer import analyze_member_query
from carenav.config import settings

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_turn_emergent_escalates(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
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

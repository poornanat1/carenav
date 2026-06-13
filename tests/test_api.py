"""FastAPI turn-endpoint tests via TestClient.

/health is hermetic. /turn is exercised on an emergent turn (stubbed generation, no DB/LLM
needed) to assert the escalation handoff serializes correctly through the response model.
"""

from fastapi.testclient import TestClient

from carenav.api.app import app
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

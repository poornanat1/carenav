"""ModelGateway tests via the offline stub generator — no key/network required."""

from carenav.config import settings
from carenav.models import ModelGateway


def test_stub_generation_records_zero_cost(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    gw = ModelGateway()
    res = gw.generate("hello [CHUNK:x] world", label="t")
    assert res.text  # stub returns something
    assert res.call.backend == "stub"
    assert res.call.cost_usd == 0.0
    assert gw.ledger.total_cost_usd == 0.0


def test_prompt_capture_for_pii_sweep(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    gw = ModelGateway(capture_prompts=True)
    gw.generate("redacted prompt [MEMBER_NAME]", label="rag.generate")
    assert len(gw.captured_prompts) == 1
    assert gw.captured_prompts[0]["label"] == "rag.generate"
    assert "[MEMBER_NAME]" in gw.captured_prompts[0]["prompt"]


def test_ledger_accumulates_calls(monkeypatch):
    monkeypatch.setattr(settings, "stub_generation", True)
    gw = ModelGateway()
    gw.generate("a [CHUNK:1]")
    gw.generate("b [CHUNK:2]")
    assert len(gw.ledger.calls) == 2
    assert gw.ledger.total_input_tokens > 0


def test_cost_pricing_for_known_model():
    from carenav.models.gateway import _cost_usd

    # 1M input + 1M output tokens at the mistral-small price.
    cost = _cost_usd("mistral-small-latest", 1_000_000, 1_000_000)
    assert round(cost, 2) == round(0.10 + 0.30, 2)

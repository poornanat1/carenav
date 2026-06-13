"""ModelGateway tests via the offline stub generator — no key/network required."""

import json

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


# --- PII detector (fine-tuned span extractor) ---


def test_parse_pii_spans_accepts_array_and_object_wrapper():
    from carenav.models.gateway import _parse_pii_spans

    arr = _parse_pii_spans('[{"start": 5, "end": 10, "label": "NAME"}]', 20)
    assert arr == [{"start": 5, "end": 10, "label": "NAME"}]
    # json_object mode wraps the array in an object.
    obj = _parse_pii_spans('{"spans": [{"start": 0, "end": 3, "label": "DOB"}]}', 20)
    assert obj == [{"start": 0, "end": 3, "label": "DOB"}]


def test_parse_pii_spans_drops_bad_label_and_out_of_range():
    from carenav.models.gateway import _parse_pii_spans

    spans = _parse_pii_spans(
        '[{"start": 0, "end": 3, "label": "SSN"}, {"start": 0, "end": 99, "label": "NAME"}]',
        5,
    )
    assert spans == []  # SSN not a model label; 0..99 exceeds text length


def test_parse_pii_spans_raises_on_garbage_so_caller_fails_safe():
    import pytest

    from carenav.models.gateway import _parse_pii_spans

    # Unparseable output must raise — the gateway catches it and returns None
    # ("detector unavailable"), never an empty "no PII found".
    with pytest.raises(json.JSONDecodeError):
        _parse_pii_spans("not json at all", 10)


def test_classify_pii_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "pii_model", None)
    monkeypatch.setattr(settings, "mistral_api_key", None)
    gw = ModelGateway()
    # None is the fall-back signal (use spaCy/regex), distinct from [] (model ran, found none).
    assert gw.classify_pii("Hi, I'm Jordan and my DOB is 3/4/80") is None


def test_classify_pii_call_is_never_captured(monkeypatch):
    # The PII tagger's input is raw PHI by design — it must never enter captured_prompts.
    monkeypatch.setattr(settings, "pii_model", None)
    gw = ModelGateway(capture_prompts=True)
    gw.classify_pii("My name is Jordan Reyes")
    assert gw.captured_prompts == []

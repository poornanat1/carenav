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


def test_every_configured_model_has_a_price():
    # Regression: the price table was once keyed on names that never matched the configured
    # Fireworks model ids, so every generation call silently fell through to the default.
    for model in (
        settings.model_small,
        settings.model_frontier,
        settings.embedding_model,
        settings.pii_base_model,
    ):
        assert model in settings.model_prices, f"no price entry for configured model {model!r}"


def test_fireworks_http_error_is_retryable():
    # The retry predicate must SEE the status code, so transient HTTP errors back off.
    from carenav.models.gateway import TransientModelError, _is_transient

    assert _is_transient(TransientModelError("rate limited", code=429))
    assert _is_transient(TransientModelError("server error", code=503))
    assert not _is_transient(TransientModelError("bad request", code=400))


# --- PII detector (fine-tuned span extractor) ---


def test_parse_pii_spans_accepts_value_array_and_object_wrapper():
    from carenav.models.gateway import _parse_pii_spans

    text = "Patient Jordan Reyes was born 3/4/1980."
    arr = _parse_pii_spans('[{"text": "Jordan Reyes", "label": "NAME"}]', text)
    assert arr == [{"start": 8, "end": 20, "label": "NAME"}]
    obj = _parse_pii_spans('{"entities": [{"text": "3/4/1980", "label": "DOB"}]}', text)
    assert obj == [{"start": 30, "end": 38, "label": "DOB"}]


def test_parse_pii_spans_supports_legacy_offsets():
    from carenav.models.gateway import _parse_pii_spans

    spans = _parse_pii_spans('[{"start": 5, "end": 10, "label": "NAME"}]', 20)
    assert spans == [{"start": 5, "end": 10, "label": "NAME"}]


def test_parse_pii_spans_drops_bad_label_and_out_of_range():
    from carenav.models.gateway import _parse_pii_spans

    spans = _parse_pii_spans(
        '[{"text": "123-45-6789", "label": "SSN"}, {"start": 0, "end": 99, "label": "NAME"}]',
        5,
    )
    assert spans == []  # SSN not a model label; 0..99 exceeds text length


def test_parse_pii_spans_resolves_repeated_values_in_order():
    from carenav.models.gateway import _parse_pii_spans

    text = "Jordan called Jordan again."
    spans = _parse_pii_spans(
        '[{"text": "Jordan", "label": "NAME"}, {"text": "Jordan", "label": "NAME"}]',
        text,
    )
    assert spans == [
        {"start": 0, "end": 6, "label": "NAME"},
        {"start": 14, "end": 20, "label": "NAME"},
    ]


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


def test_classify_pii_cold_deployment_fails_fast_to_none(monkeypatch):
    # A scaled-to-zero LoRA (503 DEPLOYMENT_SCALING_UP) must NOT be retried inline — warming
    # an H200 takes minutes and would hang the turn. It reports the detector unavailable
    # (None → caller falls back to spaCy+regex) after a single HTTP call, not a retry ladder.
    import httpx

    monkeypatch.setattr(settings, "fireworks_api_key", "fake")
    monkeypatch.setattr(
        settings, "pii_model", "accounts/x/models/y#accounts/x/deployments/z"
    )
    cold = httpx.Response(
        503,
        request=httpx.Request("POST", "https://api.fireworks.ai/x"),
        json={"error": {"code": "DEPLOYMENT_SCALING_UP", "message": "scaling up"}},
    )
    calls = {"n": 0}

    def _post(*_a, **_k):
        calls["n"] += 1
        return cold

    monkeypatch.setattr("carenav.models.gateway.httpx.post", _post)
    gw = ModelGateway()
    monkeypatch.setattr(gw, "using_real_models", lambda: True)
    assert gw.classify_pii("My name is Jane Doe") is None
    assert calls["n"] == 1  # no retry backoff on a cold deployment


def test_classify_pii_call_is_never_captured(monkeypatch):
    # The PII tagger's input is raw PHI by design — it must never enter captured_prompts.
    monkeypatch.setattr(settings, "pii_model", None)
    gw = ModelGateway(capture_prompts=True)
    gw.classify_pii("My name is Jordan Reyes")
    assert gw.captured_prompts == []

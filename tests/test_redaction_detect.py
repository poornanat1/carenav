"""Tests for the three-layer PII detector. Layers 1 (field) + 3 (regex) run offline;
layer 2 (model) is exercised via a fake gateway so no key/network is needed."""

from carenav.redaction import entities as E
from carenav.redaction.detect import detect


def _types(spans):
    return sorted(s.type for s in spans)


def test_regex_layer_catches_email_phone_ssn():
    text = "Reach me at jordan@example.com or 555-123-4567, SSN 123-45-6789."
    spans = detect(text)
    assert E.EMAIL in _types(spans)
    assert E.PHONE in _types(spans)
    assert E.SSN in _types(spans)


def test_field_layer_matches_known_member_values():
    text = "Hi, this is Jordan Reyes, I live at 12 Oak St."
    spans = detect(text, known_values={E.NAME: "Jordan Reyes", E.ADDRESS: "12 Oak St"})
    by_type = {s.type: s for s in spans}
    assert by_type[E.NAME].value == "Jordan Reyes"
    assert by_type[E.ADDRESS].value == "12 Oak St"


def test_field_match_is_case_insensitive():
    spans = detect("my name is jordan reyes", known_values={E.NAME: "Jordan Reyes"})
    assert any(s.type == E.NAME for s in spans)


def test_member_id_caught_by_regex_without_known_values():
    spans = detect("Member M001234 here.")
    assert any(s.type == E.MEMBER_ID and s.value == "M001234" for s in spans)


def test_no_pii_returns_empty():
    assert detect("Is an MRI covered under my plan?") == []


def test_overlapping_spans_merge_longest_wins():
    # Field layer matches the full name; a hypothetical second layer the first name only.
    # Simulate by giving two known values that overlap; merge keeps the longer.
    text = "Patient Jordan Reyes is here."
    spans = detect(text, known_values={E.NAME: "Jordan Reyes", "NAME_PARTIAL": "Jordan"})
    name_spans = [s for s in spans if s.value in ("Jordan", "Jordan Reyes")]
    assert len(name_spans) == 1
    assert name_spans[0].value == "Jordan Reyes"  # longer span wins


class _FakeGateway:
    """Stand-in for ModelGateway.classify_pii — returns canned spans or None (unavailable)."""

    def __init__(self, spans):
        self._spans = spans

    def classify_pii(self, text):
        return self._spans


def test_model_layer_adds_free_text_spans():
    text = "My doctor Dr. Patel ordered an MRI."
    gw = _FakeGateway([{"start": 10, "end": 19, "label": E.PROVIDER_NAME}])
    spans = detect(text, gateway=gw)
    assert any(s.type == E.PROVIDER_NAME and s.value == "Dr. Patel" for s in spans)


def test_model_unavailable_falls_back_to_layers_1_and_3():
    # gateway.classify_pii returns None (no key/model) → layer 2 contributes nothing,
    # but regex still catches the email. The gate does not depend on the model.
    text = "Email jordan@example.com about my claim."
    gw = _FakeGateway(None)
    spans = detect(text, gateway=gw)
    assert any(s.type == E.EMAIL for s in spans)

"""Tests for tokenization, rehydration, and the redact() round-trip. Offline."""

from carenav.redaction import PiiMap, redact, rehydrate
from carenav.redaction import entities as E
from carenav.redaction.entities import Span
from carenav.redaction.tokenize import audit_entries, tokenize


def test_tokenize_replaces_span_with_placeholder():
    text = "My name is Jordan Reyes."
    spans = [Span(type=E.NAME, start=11, end=23, value="Jordan Reyes")]
    pm = PiiMap()
    out = tokenize(text, spans, pm)
    assert out == "My name is [NAME_1]."
    assert pm.value("[NAME_1]") == "Jordan Reyes"


def test_same_value_gets_same_token_stable_within_session():
    pm = PiiMap()
    text = "Jordan called. Then Jordan left."
    spans = [
        Span(type=E.NAME, start=0, end=6, value="Jordan"),
        Span(type=E.NAME, start=20, end=26, value="Jordan"),
    ]
    out = tokenize(text, spans, pm)
    # Both occurrences → the same token (model can reason about "the same person").
    assert out == "[NAME_1] called. Then [NAME_1] left."


def test_distinct_values_increment_per_type():
    pm = PiiMap()
    spans = [
        Span(type=E.NAME, start=0, end=5, value="Alice"),
        Span(type=E.NAME, start=10, end=13, value="Bob"),
        Span(type=E.DOB, start=19, end=29, value="1980-03-04"),
    ]
    tokenize("Alice and Bob born 1980-03-04", spans, pm)
    assert pm.value("[NAME_1]") == "Alice"
    assert pm.value("[NAME_2]") == "Bob"
    assert pm.value("[DOB_1]") == "1980-03-04"


def test_multiple_spans_offsets_stay_valid():
    # Right-to-left application keeps earlier offsets correct even with different-length tokens.
    text = "Alice (born 1980-03-04) lives here."
    spans = [
        Span(type=E.NAME, start=0, end=5, value="Alice"),
        Span(type=E.DOB, start=12, end=22, value="1980-03-04"),
    ]
    pm = PiiMap()
    out = tokenize(text, spans, pm)
    assert out == "[NAME_1] (born [DOB_1]) lives here."


def test_rehydrate_is_inverse_of_tokenize():
    text = "Jordan Reyes, DOB 1980-03-04."
    spans = [
        Span(type=E.NAME, start=0, end=12, value="Jordan Reyes"),
        Span(type=E.DOB, start=18, end=28, value="1980-03-04"),
    ]
    pm = PiiMap()
    redacted = tokenize(text, spans, pm)
    assert "[NAME_1]" in redacted and "[DOB_1]" in redacted
    assert rehydrate(redacted, pm) == text


def test_audit_entries_carry_no_values():
    spans = [Span(type=E.NAME, start=11, end=23, value="Jordan Reyes", source="user_text")]
    entries = audit_entries(spans)
    assert entries[0].type == E.NAME
    assert entries[0].source == "user_text"
    assert (entries[0].start, entries[0].end) == (11, 23)
    # The dataclass must not expose the value anywhere.
    assert "Jordan" not in repr(entries[0])


def test_redact_roundtrip_via_public_api():
    text = "Email jordan@example.com about member M001234."
    pm = PiiMap()
    redacted, audit = redact(text, pm)  # no gateway → layers 1+3 only
    assert "jordan@example.com" not in redacted
    assert "M001234" not in redacted
    assert "[EMAIL_1]" in redacted and "[MEMBER_ID_1]" in redacted
    assert rehydrate(redacted, pm) == text
    assert {e.type for e in audit} == {E.EMAIL, E.MEMBER_ID}

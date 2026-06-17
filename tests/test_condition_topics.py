"""Coverage tests for condition_topics: every clinical Synthea diagnosis must map to a KB
topic, and every topic must be backed by a real corpus doc. No DB/network required.

The fixture tests/fixtures/synthea_clinical_codes.json is a vendored snapshot of the
distinct clinical condition codes a real Synthea NJ run produced, so the coverage check is
hermetic. If a future Synthea run introduces a new clinical code that doesn't classify,
add a rule to condition_topics._RULES (it will fall through to general-symptoms otherwise,
which the catch-all guarantees — so the real risk this guards is a NON-clinical code being
treated as clinical or vice-versa)."""

import json
from pathlib import Path

from carenav.data import condition_topics

_FIXTURE = Path(__file__).parent / "fixtures" / "synthea_clinical_codes.json"
_CORPUS = (
    Path(__file__).parent.parent
    / "src" / "carenav" / "rag" / "corpus" / "consumer_health"
)
_CONDITION_INDEX = _CORPUS / "synthea-condition-index.md"


def _clinical_codes():
    return json.loads(_FIXTURE.read_text())


def test_every_clinical_condition_maps_to_a_topic():
    unmapped = [
        c["display"]
        for c in _clinical_codes()
        if condition_topics.topic_for(c["display"]) is None
    ]
    assert unmapped == [], f"{len(unmapped)} clinical conditions have no KB topic: {unmapped[:10]}"


def test_every_used_topic_has_a_corpus_doc():
    used = {condition_topics.topic_for(c["display"]) for c in _clinical_codes()}
    used.discard(None)
    missing = [t for t in used if not (_CORPUS / f"{t}.md").is_file()]
    assert missing == [], f"topics with no corpus doc: {missing}"


def test_declared_topics_match_corpus_docs():
    # Every topic declared in TOPICS should have a corpus file (consumer-health doc).
    missing = [
        t for t, stem in condition_topics.TOPICS.items()
        if not (_CORPUS / f"{stem}.md").is_file()
    ]
    assert missing == [], f"declared topics missing a corpus doc: {missing}"


def test_social_findings_are_not_clinical():
    for display in [
        "Full-time employment (finding)",
        "Received higher education (finding)",
        "Has a criminal record (finding)",
        "Stress (finding)",
        "Medication review due (situation)",
    ]:
        assert condition_topics.topic_for(display) is None
        assert condition_topics.is_clinical(display) is False


def test_known_conditions_classify_sensibly():
    cases = {
        "Diabetes mellitus type 2 (disorder)": "type-2-diabetes",
        "Acute bronchitis (disorder)": "upper-respiratory-infection",
        "Chronic kidney disease stage 3 (disorder)": "chronic-kidney-disease",
        "Gingivitis (disorder)": "dental-oral-health",
        "Fracture of ankle (disorder)": "injuries-fractures",
        "Major depressive disorder (disorder)": "depression-anxiety",
        "Normal pregnancy (finding)": "pregnancy",
        "Non-small cell lung cancer (disorder)": "cancer",
    }
    for display, expected in cases.items():
        assert condition_topics.topic_for(display) == expected, display


def test_condition_index_names_every_clinical_display():
    text = _CONDITION_INDEX.read_text()
    missing = [
        c["display"]
        for c in _clinical_codes()
        if condition_topics.topic_for(c["display"]) is not None and c["display"] not in text
    ]
    assert missing == [], f"condition index missing clinical labels: {missing[:10]}"

"""Coverage tests for drug_topics: every Synthea medication must map to a drug KB topic,
and every topic must be backed by a real drug_label corpus doc. No DB/network required.

tests/fixtures/synthea_medications.json is a vendored snapshot of the distinct medication
descriptions a real Synthea NJ run produced, so the coverage check is hermetic."""

import json
from pathlib import Path

from carenav.data import drug_topics

_FIXTURE = Path(__file__).parent / "fixtures" / "synthea_medications.json"
_CORPUS = (
    Path(__file__).parent.parent / "src" / "carenav" / "rag" / "corpus" / "drug_label"
)


def _meds():
    return json.loads(_FIXTURE.read_text())


def test_every_medication_maps_to_a_topic():
    unmapped = [m["desc"] for m in _meds() if drug_topics.topic_for(m["desc"]) is None]
    assert unmapped == [], f"{len(unmapped)} medications have no drug topic: {unmapped[:10]}"


def test_every_used_topic_has_a_corpus_doc():
    used = {drug_topics.topic_for(m["desc"]) for m in _meds()}
    used.discard(None)
    missing = [t for t in used if not (_CORPUS / f"{drug_topics.TOPICS[t]}.md").is_file()]
    assert missing == [], f"drug topics with no corpus doc: {missing}"


def test_declared_topics_match_corpus_docs():
    missing = [
        t for t, stem in drug_topics.TOPICS.items()
        if not (_CORPUS / f"{stem}.md").is_file()
    ]
    assert missing == [], f"declared drug topics missing a corpus doc: {missing}"


def test_known_drugs_classify_sensibly():
    cases = {
        "24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet": "metformin",
        "atorvastatin 40 MG Oral Tablet": "statins",
        "amLODIPine 2.5 MG Oral Tablet": "blood-pressure-medications",
        "Hydrochlorothiazide 25 MG Oral Tablet": "diuretics",
        "Warfarin Sodium 5 MG Oral Tablet": "anticoagulants-antiplatelets",
        "Acetaminophen 325 MG / Oxycodone Hydrochloride 10 MG Oral Tablet [Percocet]":
            "opioid-pain-medications",
        "Ibuprofen 400 MG Oral Tablet [Ibu]": "nsaids-pain-relievers",
        "Amoxicillin 500 MG Oral Tablet": "antibiotics",
        "Cisplatin 50 MG Injection": "chemotherapy",
        "1 ML Epoetin Alfa 4000 UNT/ML Injection [Epogen]": "anemia-medications",
    }
    for desc, expected in cases.items():
        assert drug_topics.topic_for(desc) == expected, desc

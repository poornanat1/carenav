"""Medication → drug KB topic classification covering every Synthea prescription.

Real Synthea prescribes ~190 distinct medication strings (by brand/strength/form). Rather
than one KB doc per string, medications are grouped into drug-class TOPICS (e.g. all the
"-statin" drugs → "statins", every ACE inhibitor / ARB / beta blocker / diuretic / CCB →
"blood-pressure-medications"), each backed by a drug_label corpus doc anchored on the most
common member of the class. `topic_for()` classifies any medication DESCRIPTION into one of
these topics so every prescription lines up with retrievable drug information.

Coverage is asserted by tests against a vendored snapshot of the medication universe, so a
new unmapped drug is caught rather than silently dropped (a clinical catch-all keeps total
coverage at 100%, so the real guard is that a drug lands in the *right* class).
"""

from __future__ import annotations

# topic → drug_label corpus doc_id stem (corpus/drug_label/<stem>.md).
TOPICS: dict[str, str] = {
    "metformin": "metformin",
    "insulin": "insulin",
    "lisinopril": "lisinopril",
    "blood-pressure-medications": "blood-pressure-medications",
    "statins": "atorvastatin",
    "diuretics": "diuretics",
    "anticoagulants-antiplatelets": "anticoagulants-antiplatelets",
    "nitroglycerin-heart": "nitroglycerin-heart",
    "opioid-pain-medications": "opioid-pain-medications",
    "nsaids-pain-relievers": "nsaids-pain-relievers",
    "levothyroxine": "levothyroxine",
    "albuterol": "albuterol",
    "inhaled-corticosteroids": "inhaled-corticosteroids",
    "antibiotics": "antibiotics",
    "chemotherapy": "chemotherapy",
    "antidepressants": "antidepressants",
    "seizure-medications": "seizure-medications",
    "antihistamines": "antihistamines",
    "osteoporosis-medications": "osteoporosis-medications",
    "dementia-medications": "dementia-medications",
    "birth-control": "birth-control",
    "corticosteroids": "corticosteroids",
    "anemia-medications": "anemia-medications",
    "immunosuppressants": "immunosuppressants",
    "anesthesia-medications": "anesthesia-medications",
    "other-medications": "other-medications",
}

# Keyword → topic. FIRST match wins; order specific before generic. Matched
# case-insensitively as a substring of the medication DESCRIPTION.
_RULES: list[tuple[str, str]] = [
    # --- diabetes ---
    ("metformin", "metformin"),
    ("insulin", "insulin"),
    ("liraglutide", "insulin"),
    # --- statins (cholesterol) ---
    ("statin", "statins"),  # atorva/simva/prava/pitava-statin
    # --- blood pressure (ACE / ARB / beta blocker / CCB / combos) ---
    ("lisinopril", "lisinopril"),
    ("enalapril", "blood-pressure-medications"),
    ("benazepril", "blood-pressure-medications"),
    ("losartan", "blood-pressure-medications"),
    ("irbesartan", "blood-pressure-medications"),
    ("valsartan", "blood-pressure-medications"),
    ("sacubitril", "blood-pressure-medications"),
    ("amlodipine", "blood-pressure-medications"),
    ("verapamil", "blood-pressure-medications"),
    ("atenolol", "blood-pressure-medications"),
    ("metoprolol", "blood-pressure-medications"),
    ("carvedilol", "blood-pressure-medications"),
    ("bisoprolol", "blood-pressure-medications"),
    ("digoxin", "blood-pressure-medications"),
    # --- diuretics ---
    ("hydrochlorothiazide", "diuretics"),
    ("furosemide", "diuretics"),
    # --- anticoagulants / antiplatelets ---
    ("warfarin", "anticoagulants-antiplatelets"),
    ("heparin", "anticoagulants-antiplatelets"),
    ("enoxaparin", "anticoagulants-antiplatelets"),
    ("clopidogrel", "anticoagulants-antiplatelets"),
    ("prasugrel", "anticoagulants-antiplatelets"),
    ("ticagrelor", "anticoagulants-antiplatelets"),
    ("eptifibatide", "anticoagulants-antiplatelets"),
    ("bivalirudin", "anticoagulants-antiplatelets"),
    ("protamine", "anticoagulants-antiplatelets"),
    ("aspirin", "anticoagulants-antiplatelets"),
    ("alteplase", "anticoagulants-antiplatelets"),
    ("reteplase", "anticoagulants-antiplatelets"),
    # --- heart / nitrate / pressor ---
    ("nitroglycerin", "nitroglycerin-heart"),
    ("norepinephrine", "nitroglycerin-heart"),
    # --- opioid pain meds (incl. acetaminophen-opioid combos) ---
    ("oxycodone", "opioid-pain-medications"),
    ("hydrocodone", "opioid-pain-medications"),
    ("codeine", "opioid-pain-medications"),
    ("morphine", "opioid-pain-medications"),
    ("fentanyl", "opioid-pain-medications"),
    ("alfentanil", "opioid-pain-medications"),
    ("sufentanil", "opioid-pain-medications"),
    ("remifentanil", "opioid-pain-medications"),
    ("meperidine", "opioid-pain-medications"),
    ("tramadol", "opioid-pain-medications"),
    ("buprenorphine", "opioid-pain-medications"),
    # --- NSAIDs / non-opioid pain / antitussive ---
    ("ibuprofen", "nsaids-pain-relievers"),
    ("naproxen", "nsaids-pain-relievers"),
    ("acetaminophen", "nsaids-pain-relievers"),
    ("dextromethorphan", "nsaids-pain-relievers"),
    # --- thyroid ---
    ("levothyroxine", "levothyroxine"),
    # --- respiratory: bronchodilator vs inhaled steroid ---
    ("albuterol", "albuterol"),
    ("fluticasone", "inhaled-corticosteroids"),
    ("salmeterol", "inhaled-corticosteroids"),
    ("budesonide", "inhaled-corticosteroids"),
    # --- antibiotics / antimicrobials ---
    ("amoxicillin", "antibiotics"),
    ("penicillin", "antibiotics"),
    ("ampicillin", "antibiotics"),
    ("cephalexin", "antibiotics"),
    ("cefazolin", "antibiotics"),
    ("cefuroxime", "antibiotics"),
    ("ciprofloxacin", "antibiotics"),
    ("doxycycline", "antibiotics"),
    ("nitrofurantoin", "antibiotics"),
    ("fosfomycin", "antibiotics"),
    ("sulfamethoxazole", "antibiotics"),
    ("trimethoprim", "antibiotics"),
    ("vancomycin", "antibiotics"),
    ("piperacillin", "antibiotics"),
    ("clavulanate", "antibiotics"),
    # --- chemotherapy / oncology ---
    ("cisplatin", "chemotherapy"),
    ("paclitaxel", "chemotherapy"),
    ("docetaxel", "chemotherapy"),
    ("doxorubicin", "chemotherapy"),
    ("etoposide", "chemotherapy"),
    ("oxaliplatin", "chemotherapy"),
    ("bevacizumab", "chemotherapy"),
    ("leucovorin", "chemotherapy"),
    ("abemaciclib", "chemotherapy"),
    ("letrozole", "chemotherapy"),
    ("tamoxifen", "chemotherapy"),
    ("leuprolide", "chemotherapy"),
    # --- antidepressants ---
    ("fluoxetine", "antidepressants"),
    # --- seizure / benzodiazepine ---
    ("carbamazepine", "seizure-medications"),
    ("clonazepam", "seizure-medications"),
    ("diazepam", "seizure-medications"),
    ("midazolam", "seizure-medications"),
    # --- antihistamines / allergy ---
    ("cetirizine", "antihistamines"),
    ("loratadine", "antihistamines"),
    ("fexofenadine", "antihistamines"),
    ("diphenhydramine", "antihistamines"),
    ("chlorpheniramine", "antihistamines"),
    ("astemizole", "antihistamines"),
    ("epinephrine", "antihistamines"),  # allergy auto-injector
    # --- osteoporosis ---
    ("alendronic", "osteoporosis-medications"),
    ("alendronate", "osteoporosis-medications"),
    # --- dementia ---
    ("donepezil", "dementia-medications"),
    ("memantine", "dementia-medications"),
    ("galantamine", "dementia-medications"),
    # --- contraceptives / hormonal ---
    ("ethinyl estradiol", "birth-control"),
    ("estradiol", "birth-control"),
    ("levonorgestrel", "birth-control"),
    ("norethindrone", "birth-control"),
    ("norgestimate", "birth-control"),
    ("norelgestromin", "birth-control"),
    ("etonogestrel", "birth-control"),
    ("drospirenone", "birth-control"),
    ("dienogest", "birth-control"),
    ("medroxyprogesterone", "birth-control"),
    # --- corticosteroids (systemic/topical) ---
    ("prednisone", "corticosteroids"),
    ("hydrocortisone", "corticosteroids"),
    # --- anemia supports ---
    ("epoetin", "anemia-medications"),
    ("ferrous sulfate", "anemia-medications"),
    ("vitamin b12", "anemia-medications"),
    # --- transplant immunosuppressants ---
    ("tacrolimus", "immunosuppressants"),
    # --- anesthesia / perioperative ---
    ("propofol", "anesthesia-medications"),
    ("isoflurane", "anesthesia-medications"),
    ("sevoflurane", "anesthesia-medications"),
    ("desflurane", "anesthesia-medications"),
    ("rocuronium", "anesthesia-medications"),
    ("ondansetron", "anesthesia-medications"),
    ("proparacaine", "anesthesia-medications"),
    ("tropicamide", "anesthesia-medications"),
    # --- misc / vehicles ---
    ("sodium fluoride", "other-medications"),
    ("sodium chloride", "other-medications"),
]


def topic_for(description: str | None) -> str | None:
    """Classify a medication DESCRIPTION into a drug KB topic.

    Returns None only for an empty description; any real drug falls through to
    'other-medications' so coverage is total.
    """
    if not description:
        return None
    low = description.lower()
    for kw, topic in _RULES:
        if kw in low:
            return topic
    return "other-medications"


__all__ = ["TOPICS", "topic_for"]

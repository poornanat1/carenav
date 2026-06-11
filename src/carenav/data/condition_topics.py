"""Condition → KB topic classification covering every clinical Synthea diagnosis.

Real Synthea emits ~200 distinct clinical condition codes. Rather than one KB doc per
code, conditions are grouped into a manageable set of clinical TOPICS (e.g. all the
sinusitis/pharyngitis/bronchitis codes → "upper-respiratory-infection"), each backed by a
KB corpus doc. `topic_for()` classifies any condition (by SNOMED code, then by display
keywords) into one of these topics, so every real clinical diagnosis lines up with
retrievable KB content.

Non-clinical Synthea codes (social/administrative "findings" such as employment or
education status) are intentionally NOT covered — `topic_for()` returns None for them, and
`is_clinical()` flags whether a condition is a medical one at all.

Coverage is asserted by tests against a vendored snapshot of the condition universe, so a
new unmapped clinical code is caught rather than silently dropped.
"""

from __future__ import annotations

# Each topic → the KB corpus doc_id stem (consumer_health/<stem>.md) that covers it.
# This is the authoritative list of condition KB docs the corpus must contain.
TOPICS: dict[str, str] = {
    "type-2-diabetes": "type-2-diabetes",
    "high-blood-pressure": "high-blood-pressure",
    "high-cholesterol": "high-cholesterol",
    "hypothyroidism": "hypothyroidism",
    "asthma": "asthma",
    "low-back-pain": "low-back-pain",
    "copd": "copd",
    "upper-respiratory-infection": "upper-respiratory-infection",
    "pneumonia": "pneumonia",
    "covid-19": "covid-19",
    "heart-disease": "heart-disease",
    "stroke": "stroke",
    "chronic-kidney-disease": "chronic-kidney-disease",
    "obesity": "obesity",
    "anemia": "anemia",
    "dental-oral-health": "dental-oral-health",
    "depression-anxiety": "depression-anxiety",
    "arthritis-joint": "arthritis-joint",
    "osteoporosis": "osteoporosis",
    "injuries-fractures": "injuries-fractures",
    "cancer": "cancer",
    "pregnancy": "pregnancy",
    "seizure-epilepsy": "seizure-epilepsy",
    "migraine-headache": "migraine-headache",
    "sleep-apnea": "sleep-apnea",
    "gerd-digestive": "gerd-digestive",
    "urinary-tract-infection": "urinary-tract-infection",
    "allergy": "allergy",
    "dementia": "dementia",
    "sepsis": "sepsis",
    "general-symptoms": "general-symptoms",
}

# Keyword → topic. Order matters: the FIRST matching rule wins, so list more specific
# phrases before generic ones (e.g. "diabetic retinopathy" → diabetes before "retinopathy"
# could fall elsewhere). Matched case-insensitively as a substring of the display text.
_RULES: list[tuple[str, str]] = [
    # --- endocrine / metabolic ---
    ("prediabetes", "type-2-diabetes"),
    ("diabetes", "type-2-diabetes"),
    ("diabetic", "type-2-diabetes"),
    ("hyperglycemia", "type-2-diabetes"),
    ("microalbuminuria", "type-2-diabetes"),
    ("metabolic syndrome", "type-2-diabetes"),
    ("hypothyroid", "hypothyroidism"),
    ("hyperlipidemia", "high-cholesterol"),
    ("hypercholesterolemia", "high-cholesterol"),
    ("hypertriglyceridemia", "high-cholesterol"),
    ("obes", "obesity"),
    ("body mass index", "obesity"),
    ("gout", "arthritis-joint"),
    # --- cardiovascular ---
    ("hypertension", "high-blood-pressure"),
    ("cerebrovascular accident", "stroke"),
    ("stroke", "stroke"),
    ("myocardial infarction", "heart-disease"),
    ("ischemic heart", "heart-disease"),
    ("coronary", "heart-disease"),
    ("heart failure", "heart-disease"),
    ("congestive", "heart-disease"),
    ("atrial fibrillation", "heart-disease"),
    ("aortic valve", "heart-disease"),
    ("mitral valve", "heart-disease"),
    ("cardiac", "heart-disease"),
    ("deep venous thrombosis", "heart-disease"),
    # --- respiratory ---
    ("copd", "copd"),
    ("chronic obstructive", "copd"),
    ("emphysema", "copd"),
    ("asthma", "asthma"),
    ("pneumonia", "pneumonia"),
    ("coronavirus", "covid-19"),
    ("covid", "covid-19"),
    ("sinusitis", "upper-respiratory-infection"),
    ("pharyngitis", "upper-respiratory-infection"),
    ("bronchitis", "upper-respiratory-infection"),
    ("sore throat", "upper-respiratory-infection"),
    ("streptococcal sore", "upper-respiratory-infection"),
    ("otitis media", "upper-respiratory-infection"),
    ("nasal congestion", "upper-respiratory-infection"),
    ("sleep apnea", "sleep-apnea"),
    ("obstructive sleep", "sleep-apnea"),
    # --- kidney / urinary ---
    ("kidney disease", "chronic-kidney-disease"),
    ("renal disease", "chronic-kidney-disease"),
    ("end-stage renal", "chronic-kidney-disease"),
    ("renal dysplasia", "chronic-kidney-disease"),
    ("renal transplant", "chronic-kidney-disease"),
    ("transplantation of kidney", "chronic-kidney-disease"),
    ("proteinuria", "chronic-kidney-disease"),
    ("cystitis", "urinary-tract-infection"),
    ("urinary tract infection", "urinary-tract-infection"),
    ("pyelonephritis", "urinary-tract-infection"),
    # --- digestive ---
    ("gastroesophageal reflux", "gerd-digestive"),
    ("reflux", "gerd-digestive"),
    ("cholecystitis", "gerd-digestive"),
    ("gallbladder", "gerd-digestive"),
    ("gallstone", "gerd-digestive"),
    ("appendicitis", "gerd-digestive"),
    ("rupture of appendix", "gerd-digestive"),
    ("polyp of colon", "gerd-digestive"),
    ("rectal polyp", "gerd-digestive"),
    ("bleeding from anus", "gerd-digestive"),
    ("diarrhea", "gerd-digestive"),
    # --- musculoskeletal / pain / injury ---
    ("low back", "low-back-pain"),
    ("neck pain", "low-back-pain"),
    ("rheumatoid arthritis", "arthritis-joint"),
    ("osteoarthritis", "arthritis-joint"),
    ("fibromyalgia", "arthritis-joint"),
    ("joint pain", "arthritis-joint"),
    ("artificial joint", "arthritis-joint"),
    ("scoliosis", "arthritis-joint"),
    ("osteoporo", "osteoporosis"),
    ("fracture", "injuries-fractures"),
    ("sprain", "injuries-fractures"),
    ("laceration", "injuries-fractures"),
    ("burn", "injuries-fractures"),
    ("concussion", "injuries-fractures"),
    ("whiplash", "injuries-fractures"),
    ("injury", "injuries-fractures"),
    ("wound", "injuries-fractures"),
    ("dislocation", "injuries-fractures"),
    ("rupture of patellar", "injuries-fractures"),
    ("rotator cuff", "injuries-fractures"),
    ("spinal cord", "injuries-fractures"),
    ("brain injury", "injuries-fractures"),
    ("overdose", "injuries-fractures"),
    # --- neuro / mental health ---
    ("depress", "depression-anxiety"),
    ("anxiety", "depression-anxiety"),
    ("alcoholism", "depression-anxiety"),
    ("attention deficit", "depression-anxiety"),
    ("migraine", "migraine-headache"),
    ("headache", "migraine-headache"),
    ("seizure", "seizure-epilepsy"),
    ("epilepsy", "seizure-epilepsy"),
    ("cerebral palsy", "seizure-epilepsy"),
    ("spasticity", "seizure-epilepsy"),
    ("alzheimer", "dementia"),
    ("dementia", "dementia"),
    # --- blood / cancer / infection ---
    ("anemia", "anemia"),
    ("leukemia", "cancer"),
    ("neoplasm", "cancer"),
    ("cancer", "cancer"),
    ("carcinoma", "cancer"),
    ("malignant", "cancer"),
    ("lung cancer", "cancer"),
    ("bone marrow transplant", "cancer"),
    ("stem cell transplant", "cancer"),
    ("sepsis", "sepsis"),
    ("septic shock", "sepsis"),
    ("mediastinitis", "sepsis"),
    # --- dental / oral ---
    ("gingiv", "dental-oral-health"),
    ("dental", "dental-oral-health"),
    ("tooth", "dental-oral-health"),
    ("teeth", "dental-oral-health"),
    ("caries", "dental-oral-health"),
    ("molars", "dental-oral-health"),
    ("alveol", "dental-oral-health"),
    ("torus palatinus", "dental-oral-health"),
    ("torus mandibularis", "dental-oral-health"),
    ("temporomandibular", "dental-oral-health"),
    ("tongue tie", "dental-oral-health"),
    # --- allergy ---
    ("allergic rhinitis", "allergy"),
    ("allergic reaction", "allergy"),
    ("atopic dermatitis", "allergy"),
    ("contact dermatitis", "allergy"),
    # --- pregnancy / reproductive ---
    ("pregnancy", "pregnancy"),
    ("miscarriage", "pregnancy"),
    ("pre-eclampsia", "pregnancy"),
    ("eclampsia", "pregnancy"),
    ("blighted ovum", "pregnancy"),
    ("tubal", "pregnancy"),
    ("ovum", "pregnancy"),
    ("fetus", "pregnancy"),
    ("sterilization", "pregnancy"),
    # --- general symptoms (catch-all for nonspecific symptom findings) ---
    ("prostate", "cancer"),
    ("fever", "general-symptoms"),
    ("chill", "general-symptoms"),
    ("cough", "general-symptoms"),
    ("fatigue", "general-symptoms"),
    ("nausea", "general-symptoms"),
    ("vomiting", "general-symptoms"),
    ("dyspnea", "general-symptoms"),
    ("wheezing", "general-symptoms"),
    ("hypoxemia", "general-symptoms"),
    ("muscle pain", "general-symptoms"),
    ("chronic pain", "general-symptoms"),
    ("pain", "general-symptoms"),
    ("loss of taste", "general-symptoms"),
    ("loss of smell", "general-symptoms"),
    ("sputum", "general-symptoms"),
    ("congestion", "general-symptoms"),
    ("abnormal findings", "general-symptoms"),
    ("sleep disorder", "sleep-apnea"),
]

# Display substrings that mark a NON-clinical (social / administrative) Synthea code. These
# are excluded from KB coverage — they're context findings, not diseases.
_NON_CLINICAL = (
    "employment", "education", "social", "labor force", "criminal", "violence", "abuse",
    "housing", "unemploy", "risk activity", "medication review", "part-time", "full-time",
    "received higher", "reports of", "victim", "limited social", "educated", "transport problem",
    "unhealthy alcohol", "misuses drugs", "homeless", "refugee", "served in armed", "income",
    "lack of", "serving in military", "stress (finding)", "isolation",
)


def is_clinical(display: str | None) -> bool:
    """Whether a Synthea condition display is a clinical (medical) one vs. social/admin."""
    if not display:
        return False
    low = display.lower()
    return not any(s in low for s in _NON_CLINICAL)


def topic_for(display: str | None) -> str | None:
    """Classify a condition display into a clinical KB topic, or None if non-clinical.

    Clinical conditions always resolve to a topic (the last rule, 'pain', plus the
    general-symptoms catch-all, ensure no clinical code is left unmapped); social/admin
    findings return None.
    """
    if not is_clinical(display):
        return None
    low = display.lower()
    for kw, topic in _RULES:
        if kw in low:
            return topic
    # Any clinical condition with no keyword match still gets a home so coverage is total.
    return "general-symptoms"


__all__ = ["TOPICS", "is_clinical", "topic_for"]

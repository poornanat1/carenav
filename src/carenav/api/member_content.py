"""Topic-driven presentation data for the member API.

These are hand-curated demo mappings from a KB topic (see carenav.data.condition_topics)
to the medications, provider specialty, and suggested questions we surface for a member
with that topic. They are DATA, not logic — kept out of members.py so the presentation
helpers stay small and so editing the demo content doesn't touch control flow. Topic keys
must exist in condition_topics.TOPICS.
"""

from __future__ import annotations

from carenav.api.schemas import SuggestedQuestion

# Topic → medications typically associated with it, in display order. A member's medication
# list is the union over their topics (deduped, order-preserving).
MEDICATIONS_BY_TOPIC: dict[str, list[str]] = {
    "type-2-diabetes": ["Metformin"],
    "high-blood-pressure": ["Lisinopril"],
    "high-cholesterol": ["Atorvastatin"],
    "asthma": ["Albuterol inhaler"],
    "copd": ["Albuterol inhaler"],
    "pregnancy": ["Prenatal vitamins"],
    "anemia": ["Iron supplement"],
    "urinary-tract-infection": ["Antibiotics"],
    "low-back-pain": ["NSAID pain reliever"],
    "arthritis-joint": ["NSAID pain reliever"],
}

NO_MEDICATIONS = "No active medication data loaded"

# Topic → the provider specialty we'd recommend. First matching topic wins (the member's
# topics are checked in their own order). Several topics can share a specialty.
SPECIALTY_BY_TOPIC: dict[str, str] = {
    "heart-disease": "Cardiology",
    "high-blood-pressure": "Cardiology",
    "high-cholesterol": "Cardiology",
    "type-2-diabetes": "Endocrinology",
    "asthma": "Pulmonary Disease",
    "copd": "Pulmonary Disease",
    "pneumonia": "Pulmonary Disease",
    "low-back-pain": "Orthopedic",
    "arthritis-joint": "Orthopedic",
    "osteoporosis": "Orthopedic",
    "cancer": "Oncology",
}

# Topics whose presence makes a member a richer demo profile (used to rank the member list).
HIGH_SIGNAL_TOPICS: frozenset[str] = frozenset({
    "type-2-diabetes", "high-blood-pressure", "heart-disease", "pregnancy",
    "asthma", "low-back-pain", "anemia", "urinary-tract-infection",
})


def _q(label: str, question: str, intent: str) -> SuggestedQuestion:
    return SuggestedQuestion(label=label, question=question, intent=intent)


# Topic → suggested starter questions for a member with that topic.
SUGGESTED_QUESTIONS_BY_TOPIC: dict[str, list[SuggestedQuestion]] = {
    "type-2-diabetes": [
        _q("Diabetes overview",
           "What should I know about prediabetes and type 2 diabetes?", "condition_info"),
        _q("Metformin side effects",
           "What are the common side effects of metformin?", "medication"),
        _q("Diabetes supplies",
           "Is continuous glucose monitoring covered under my plan?", "benefits"),
    ],
    "high-blood-pressure": [
        _q("Blood pressure care",
           "What should I know about high blood pressure?", "condition_info"),
        _q("BP medications",
           "What should I know about blood pressure medications?", "medication"),
    ],
    "high-cholesterol": [
        _q("Cholesterol care",
           "What should I know about high cholesterol?", "condition_info"),
        _q("Statin side effects",
           "What are common side effects of statin medications?", "medication"),
    ],
    "pregnancy": [
        _q("Prenatal coverage",
           "What prenatal services are covered under my plan?", "benefits"),
        _q("Prenatal vitamins",
           "Are prescription prenatal vitamins covered by my plan?", "medication"),
    ],
    "asthma": [
        _q("Asthma basics",
           "What should I know about asthma symptoms and care?", "condition_info"),
        _q("Inhaler info",
           "What should I know about albuterol inhalers?", "medication"),
    ],
    "low-back-pain": [
        _q("Back pain care",
           "What should I know about low back pain self-care?", "condition_info"),
        _q("MRI coverage",
           "Is an MRI covered under my plan, and does it need prior authorization?", "benefits"),
    ],
    "anemia": [
        _q("Anemia basics", "What should I know about anemia?", "condition_info"),
        _q("Iron side effects",
           "What should I know about iron supplements for anemia?", "medication"),
    ],
    "urinary-tract-infection": [
        _q("UTI care",
           "What should I know about urinary tract infection symptoms and care?",
           "condition_info"),
        _q("Antibiotics",
           "What should I know about antibiotic side effects?", "medication"),
    ],
    "chronic-kidney-disease": [
        _q("Kidney care",
           "What should I know about chronic kidney disease?", "condition_info"),
        _q("Kidney coverage",
           "What kidney-related care is covered under my plan?", "benefits"),
    ],
    "heart-disease": [
        _q("Heart disease care",
           "What should I know about heart disease and warning signs?", "condition_info"),
        _q("Cardiology coverage",
           "What cardiology care is covered under my plan?", "benefits"),
    ],
    "osteoporosis": [
        _q("Bone health", "What should I know about osteoporosis?", "condition_info"),
        _q("Bone medicines",
           "What should I know about osteoporosis medications?", "medication"),
    ],
    "upper-respiratory-infection": [
        _q("Respiratory symptoms",
           "What should I know about upper respiratory infections?", "condition_info"),
    ],
    "dental-oral-health": [
        _q("Dental coverage",
           "What dental or oral health care may be covered under my plan?", "benefits"),
    ],
    "sleep-apnea": [
        _q("Sleep apnea", "What should I know about sleep apnea?", "condition_info"),
    ],
    "general-symptoms": [
        _q("Symptoms",
           "What symptoms should I watch for, and when should I seek care?", "condition_info"),
    ],
}

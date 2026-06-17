"""Semantic query analysis for selected-member turns.

The API needs to decide whether a question should be answered from the selected member
profile, the public KB, or both. This module keeps that decision in one place: an LLM
produces a small structured analysis, while deterministic guardrails cover cases that
must not depend on model judgment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from carenav.data import condition_topics
from carenav.models import ModelGateway


@dataclass(frozen=True)
class QueryAnalysis:
    scope: str
    kind: str
    condition_topic: str | None = None
    kb_intent: str | None = None
    needs_profile: bool = False
    needs_kb: bool = False


class MemberContext(Protocol):
    name: str
    kb_topics: list[str]
    conditions: list[str]
    medications: list[str]


def _topic_label(topic: str) -> str:
    return topic.replace("-", " ").title()


def _is_educational_question(question: str) -> bool:
    low = question.lower().strip()
    educational_starts = (
        "what is ",
        "what are ",
        "what's ",
        "whats ",
        "what should i know about ",
        "what should we know about ",
        "what should someone know about ",
        "explain ",
        "tell me about ",
        "define ",
    )
    educational_patterns = (
        " meaning",
        "meaning?",
        "what does",
        "what do",
        "stand for",
    )
    return low.startswith(educational_starts) or any(
        pattern in low for pattern in educational_patterns
    )


def _mentions_selected_profile(question: str, summary: MemberContext) -> bool:
    low = question.lower()
    first_name = summary.name.split()[0].rstrip(".").lower() if summary.name else ""
    profile_cues = {
        "she",
        "her",
        "he",
        "his",
        "they",
        "them",
        "their",
        "member",
        "profile",
        "patient",
    }
    words = {word.strip(".,?!:;()[]{}'\"") for word in low.split()}
    return bool(first_name and first_name in low) or "my " in low or bool(words & profile_cues)


def _mentioned_condition_topic(question: str) -> str | None:
    low = question.lower()
    for topic in condition_topics.TOPICS:
        label = _topic_label(topic)
        candidates = {topic, topic.replace("-", " "), label.lower()}
        if any(candidate in low for candidate in candidates):
            return label
    return None


def _is_condition_presence_question(question: str) -> bool:
    low = question.lower()
    return any(
        cue in low
        for cue in (
            "does ",
            "do ",
            "has ",
            "have ",
            "history of",
            "diagnosed with",
            "profile show",
        )
    )


def _is_benefit_coverage_language(question: str) -> bool:
    low = question.lower()
    coverage_terms = (
        "covered",
        "cover ",
        "coverage for",
        "copay",
        "coinsurance",
        "prior auth",
        "prior authorization",
    )
    return any(term in low for term in coverage_terms)


def _guardrail_analysis(
    question: str,
    summary: MemberContext,
    *,
    include_soft: bool = True,
) -> QueryAnalysis | None:
    low = question.lower()
    profile_mentioned = _mentions_selected_profile(question, summary)

    if include_soft and _is_educational_question(question) and not profile_mentioned:
        return QueryAnalysis(
            scope="general",
            kind="knowledge",
            kb_intent="condition_info",
            needs_profile=False,
            needs_kb=True,
        )

    plan_terms = ["what plan", "which plan", "plan name", "enrolled in", "eligibility"]
    if any(term in low for term in plan_terms):
        return QueryAnalysis(scope="profile", kind="coverage", needs_profile=True)

    if _is_benefit_coverage_language(question):
        return QueryAnalysis(
            scope="general",
            kind="other",
            kb_intent="benefit",
            needs_profile=False,
            needs_kb=True,
        )

    if any(term in low for term in ["deductible", "out-of-pocket", "out of pocket", "oop"]):
        return QueryAnalysis(scope="profile", kind="coverage", needs_profile=True)

    risk_terms = ["risk", "at risk", "risky", "complication", "contraindication", "warning"]
    if profile_mentioned and any(term in low for term in risk_terms):
        return QueryAnalysis(
            scope="mixed",
            kind="risk",
            kb_intent="medication",
            needs_profile=True,
            needs_kb=True,
        )

    if profile_mentioned and any(term in low for term in ["recent claim", "last claim", "claims"]):
        return QueryAnalysis(scope="profile", kind="claims", needs_profile=True)

    if profile_mentioned and any(term in low for term in ["medication", "medicine", "meds"]):
        return QueryAnalysis(scope="profile", kind="medications", needs_profile=True)

    condition_topic = _mentioned_condition_topic(question)
    if (
        include_soft
        and profile_mentioned
        and condition_topic
        and _is_condition_presence_question(question)
    ):
        return QueryAnalysis(
            scope="profile",
            kind="specific_condition",
            condition_topic=condition_topic,
            needs_profile=True,
        )

    condition_terms = ["condition", "conditions", "diagnosis", "diagnoses", "medical history"]
    broad_have_question = "what" in low and "have" in low
    if (
        profile_mentioned
        and include_soft
        and not _is_educational_question(question)
        and (broad_have_question or any(term in low for term in condition_terms))
    ):
        return QueryAnalysis(scope="profile", kind="conditions", needs_profile=True)

    summary_terms = ["summarize", "summary", "overview", "profile"]
    if profile_mentioned and any(term in low for term in summary_terms):
        return QueryAnalysis(scope="profile", kind="summary", needs_profile=True)

    return None


def analyze_member_query(
    question: str, summary: MemberContext, gateway: ModelGateway | None = None
) -> QueryAnalysis:
    guardrail = _guardrail_analysis(question, summary, include_soft=gateway is None)
    if guardrail:
        return guardrail
    if gateway is None:
        return QueryAnalysis(scope="general", kind="other", needs_profile=False, needs_kb=True)

    topics = ", ".join(summary.kb_topics) if summary.kb_topics else "none"
    conditions = ", ".join(summary.conditions) if summary.conditions else "none"
    medications = ", ".join(summary.medications) if summary.medications else "none"
    first_name = summary.name.split()[0].rstrip(".").lower() if summary.name else ""
    prompt = f"""Analyze this health-navigation question for a selected synthetic member.

Return ONLY compact JSON with this shape:
{{
  "scope":"profile|general|mixed",
  "kind":"summary|conditions|coverage|claims|medications|specific_condition|risk|knowledge|other",
  "condition_topic":string|null,
  "kb_intent":"condition_info|medication|coverage|benefit|null",
  "needs_profile":true|false,
  "needs_kb":true|false
}}

Semantics:
- profile: answer from selected member facts only.
- general: answer from public health/benefits knowledge only.
- mixed: combine selected member facts with public KB facts.
- summary/conditions/coverage/claims/medications are selected-profile facts.
- coverage means selected-member account facts like deductible, out-of-pocket progress,
  current plan name, or eligibility. It is NOT for "is this service/test/procedure covered".
- service coverage questions like "is an MRI covered", "is CA-125 test covered",
  "what is my specialist copay", or "does my plan cover CGM" should be general/other,
  kb_intent benefit, needs_profile false, needs_kb true.
- specific_condition is only for presence questions like "does Martha have cancer".
- knowledge is for definitions/explanations like "what is hypertriglyceridemia",
  "History of coronary artery bypass grafting -- meaning?", or "what does CABG mean".
  Meaning/definition questions should be general/knowledge even if the phrase also appears
  in the selected member profile.
- risk is for selected-member risk questions, often mixed profile + medication/condition KB.

Examples:
- "what does she have" -> profile/conditions, needs_profile true, needs_kb false.
- "does Lindsay have cancer" -> profile/specific_condition.
- "what is hypertriglyceridemia" -> general/knowledge, kb_intent condition_info.
- "History of coronary artery bypass grafting -- meaning?" -> general/knowledge,
  kb_intent condition_info.
- "is Josh at risk for lactic acidosis" -> mixed/risk, kb_intent medication.
- "have I met my deductible" -> profile/coverage.
- "is an mri covered in my plan" -> general/other, kb_intent benefit.
- "is ca-125 test covered" -> general/other, kb_intent benefit.

Selected member display name: {summary.name}
Selected profile visible KB topics: {topics}
Selected profile conditions: {conditions}
Selected profile medication topics: {medications}
Question: {question}

JSON:"""
    try:
        raw = gateway.generate(prompt, label="api.query_analyzer").text.strip()
    except Exception:
        return QueryAnalysis(scope="general", kind="other", needs_profile=False, needs_kb=True)

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return QueryAnalysis(scope="general", kind="other", needs_profile=False, needs_kb=True)

    analysis = QueryAnalysis(
        scope=str(data.get("scope", "general")).lower(),
        kind=str(data.get("kind", "other")).lower(),
        condition_topic=data.get("condition_topic"),
        kb_intent=data.get("kb_intent"),
        needs_profile=bool(data.get("needs_profile", False)),
        needs_kb=bool(data.get("needs_kb", False)),
    )

    if first_name and first_name in question.lower() and analysis.scope != "general":
        analysis = QueryAnalysis(
            scope=analysis.scope,
            kind=analysis.kind,
            condition_topic=analysis.condition_topic,
            kb_intent=analysis.kb_intent,
            needs_profile=True,
            needs_kb=analysis.needs_kb,
        )

    if (
        _is_benefit_coverage_language(question)
        and analysis.scope == "profile"
        and analysis.kind == "coverage"
    ):
        return QueryAnalysis(
            scope="general",
            kind="other",
            kb_intent="benefit",
            needs_profile=False,
            needs_kb=True,
        )

    educational_guardrail = _guardrail_analysis(question, summary)
    if educational_guardrail and educational_guardrail.scope == "general":
        return educational_guardrail
    return analysis

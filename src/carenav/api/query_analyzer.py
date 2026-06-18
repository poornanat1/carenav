"""Semantic query analysis for selected-member turns.

The API needs to decide whether a question should be answered from the selected member
profile, the public KB, or both. This module keeps that decision in one place: an LLM
produces a small structured analysis, while deterministic guardrails cover cases that
must not depend on model judgment.
"""

from __future__ import annotations

import json
import re
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


def mentioned_condition_topic(question: str) -> str | None:
    low = question.lower()
    for topic in condition_topics.TOPICS:
        label = _topic_label(topic)
        candidates = {topic, topic.replace("-", " "), label.lower()}
        if any(candidate in low for candidate in candidates):
            return label
    return None


_TOPIC_LABELS = [_topic_label(topic) for topic in condition_topics.TOPICS]
_TOPIC_LOOKUP = {label.lower(): label for label in _TOPIC_LABELS}

_EXTRACT_PROMPT = """A health-plan member asked whether a person has a particular condition.
Map the condition they are asking about to exactly ONE label from this list, or NONE.

Labels:
{labels}

Map colloquial and clinical synonyms to the closest label (e.g. "sugar" or "diabetic" ->
Type 2 Diabetes; "tumor", "malignancy", "lung cancer" -> Cancer; "high BP" -> High Blood
Pressure). If no label clearly fits, reply NONE.

Question: {question}

Reply with ONLY the exact label text, or NONE. Nothing else."""


def llm_condition_topic(question: str, gateway: ModelGateway | None) -> str | None:
    """LLM-extract the asked-about condition, constrained to the canonical topic labels.

    Returns a label from condition_topics.TOPICS, or None. Used to recover the topic when
    the analyzer flags a presence question but leaves condition_topic unset, and to catch
    colloquial synonyms the substring matcher misses. Never raises — falls back to None so
    the caller's deterministic extractor still runs.
    """
    if gateway is None:
        return None
    prompt = _EXTRACT_PROMPT.format(
        labels="\n".join(f"- {label}" for label in _TOPIC_LABELS), question=question
    )
    try:
        raw = gateway.generate(prompt, label="api.condition_extract").text.strip()
    except Exception:
        return None
    return _TOPIC_LOOKUP.get(raw.strip().rstrip(".").lower())


def canonical_topic(value: str | None) -> str | None:
    """Map a free-text condition string to a canonical topic label, or None.

    Accepts a label ("Cancer"), a slug ("type-2-diabetes"), or a slug-with-spaces, and
    normalizes to the canonical label. Returns None for anything not in the topic set, so
    callers can tell an unmapped raw word (e.g. "tumor") from a real topic.
    """
    if not value:
        return None
    key = value.strip().rstrip(".").lower()
    return _TOPIC_LOOKUP.get(key) or _TOPIC_LOOKUP.get(key.replace("-", " "))


def resolve_condition_topic(
    question: str, analyzer_topic: str | None, gateway: ModelGateway | None
) -> str | None:
    """Best canonical topic for a presence question, trying each source in order.

    The analyzer's slot is trusted only if it maps to a real topic — it sometimes returns a
    raw word ("tumor") that isn't a topic label, which would otherwise defeat the fallback.
    Falls through to the LLM extractor (synonyms) and the deterministic matcher.
    """
    return (
        canonical_topic(analyzer_topic)
        or llm_condition_topic(question, gateway)
        or mentioned_condition_topic(question)
    )


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


_PROVIDER_SEARCH_RE = re.compile(
    r"\bfind (a |an )?(doctor|cardiologist|specialist|provider|dermatologist|"
    r"pediatrician|endocrinologist|orthopedist|orthopedic specialist|neurologist|"
    r"oncologist|ophthalmologist)\b|"
    r"\b(recommend|recommendation|suggest|suggestion)s?\b.*\b("
    r"doctor|provider|specialist|cardiologist|dermatologist|pediatrician|"
    r"endocrinologist|orthopedist|neurologist|oncologist|ophthalmologist)\b|"
    r"\b(in[- ]network|near me)\b.*\b(doctor|provider|specialist|cardiologist|"
    r"dermatologist|pediatrician|endocrinologist|orthopedist|neurologist|"
    r"oncologist|ophthalmologist)\b",
    re.IGNORECASE,
)


def is_provider_search_question(question: str) -> bool:
    return bool(_PROVIDER_SEARCH_RE.search(question))


_PROVIDER_DETAIL_RE = re.compile(
    r"^\s*(tell me (more )?about|who('?s| is)|more about|what about|details? (on|about)|"
    r"info(rmation)? (on|about))\s+(dr\.?\s+)?(?P<name>[a-z][a-z.'\- ]+?)\s*\??$",
    re.IGNORECASE,
)


def provider_detail_name(question: str) -> str | None:
    """Extract a candidate provider name from a 'tell me about <name>' question.

    Returns the trailing name phrase when the question is a person-detail ask and does NOT
    resolve to a condition topic (those stay educational/KB). The returned string is only a
    candidate — the caller confirms it against the in-network provider list before answering.
    """
    if mentioned_condition_topic(question) or _is_benefit_coverage_language(question):
        return None
    match = _PROVIDER_DETAIL_RE.match(question.strip())
    if not match:
        return None
    name = match.group("name").strip()
    # Reject account/coverage phrases ("my deductible", "this plan") — those are not names
    # and have their own guardrails further down.
    name_words = set(name.lower().split())
    account_words = {
        "my", "deductible", "plan", "claim", "claims", "coverage", "copay", "benefit",
        "benefits", "medication", "medications", "condition", "conditions", "profile",
        "account", "this", "that",
    }
    if name_words & account_words:
        return None
    # A single short word is too ambiguous to treat as a provider name.
    if len(name.split()) < 2 and len(name) < 4:
        return None
    return name


def _guardrail_analysis(
    question: str,
    summary: MemberContext,
    *,
    include_soft: bool = True,
) -> QueryAnalysis | None:
    low = question.lower()
    profile_mentioned = _mentions_selected_profile(question, summary)

    if is_provider_search_question(question):
        return QueryAnalysis(
            scope="profile",
            kind="provider_search",
            needs_profile=True,
        )

    if provider_detail_name(question):
        return QueryAnalysis(
            scope="profile",
            kind="provider_detail",
            needs_profile=True,
        )

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

    condition_topic = mentioned_condition_topic(question)
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

    # Presence questions ("does hilton have high sugar") that the LLM mislabeled as a
    # generic conditions/other listing are re-routed to specific_condition when a topic
    # resolves — including colloquial synonyms the analyzer's own slot missed. Definitions
    # and benefit/coverage questions are already handled above, so they can't reach here.
    if (
        analysis.scope != "general"
        and analysis.kind not in {"specific_condition", "risk"}
        and _is_condition_presence_question(question)
        and _mentions_selected_profile(question, summary)
        and not _is_educational_question(question)
    ):
        resolved = resolve_condition_topic(question, analysis.condition_topic, gateway)
        if resolved:
            return QueryAnalysis(
                scope="profile",
                kind="specific_condition",
                condition_topic=resolved,
                needs_profile=True,
            )
    return analysis

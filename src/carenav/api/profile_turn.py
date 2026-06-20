"""Selected-member profile answering for the API."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from carenav.agents import resolve_member_ref, specialty_hint
from carenav.agents.contracts import ProviderSearchInput, ProviderSearchOutput
from carenav.agents.providers import provider_lookup_by_name, provider_search
from carenav.api.members import load_member_summary, topic_label
from carenav.api.query_analyzer import (
    QueryAnalysis,
    analyze_member_query,
    provider_detail_name,
    resolve_condition_topic,
)
from carenav.api.schemas import MemberSummary
from carenav.data import condition_topics
from carenav.data.db import session_scope
from carenav.data.models import Member
from carenav.models import ModelGateway
from carenav.orchestrator.state import ConfidenceBreakdown, TurnResult
from carenav.rag import retrieval
from carenav.rag.agent import Citation, generate_grounded
from carenav.rag.citations import format_citation
from carenav.rag.retrieval import Hit

# All profile answers carry full confidence (they're deterministic profile facts).
_FULL_CONFIDENCE = ConfidenceBreakdown(
    intent_conf=1.0, retrieval_conf=1.0, tool_conf=1.0, self_eval=1.0
)
_PROFILE_CITATION = format_citation("tool:member_profile")


def _citations(hits: list[Hit]) -> list[Citation]:
    return [Citation(h.chunk_id, h.title, h.source_url, h.section_path) for h in hits]


def _ok_result(
    *,
    question: str,
    answer: str,
    citations: list[Citation],
    gateway: ModelGateway,
    intent: str = "member_profile",
    tier_used: str = "small",
    rag_answers=None,
) -> TurnResult:
    """A grounded, non-escalated profile/provider answer with the shared boilerplate filled."""
    return TurnResult(
        question=question,
        intent=intent,
        sub_questions=[question],
        answer=answer,
        citations=citations,
        grounded=True,
        escalated=False,
        handoff=None,
        confidence=_FULL_CONFIDENCE,
        tier_used=tier_used,
        safety_flag="none",
        cost_usd=gateway.ledger.total_cost_usd,
        rag_answers=rag_answers or [],
    )


def _escalated_result(question: str, intent: str, gateway: ModelGateway) -> TurnResult:
    """A profile turn that can't be answered from data and must go to a human."""
    return TurnResult(
        question=question,
        intent=intent,
        sub_questions=[question],
        answer="",
        citations=[],
        grounded=False,
        escalated=True,
        handoff=None,
        confidence=ConfidenceBreakdown(intent_conf=1.0, tool_conf=0.0),
        tier_used="human",
        safety_flag="none",
        cost_usd=gateway.ledger.total_cost_usd,
        rag_answers=[],
    )


def _profile_hit(summary: MemberSummary) -> Hit:
    present_topics = set(summary.kb_topics)
    topic_lines = [
        f"{topic_label(topic)} profile signal: "
        f"{'present' if topic_label(topic) in present_topics else 'absent'}."
        for topic in condition_topics.TOPICS
    ]
    claim_lines = [
        (
            f"Recent claim: {claim.description}; status {claim.status}; "
            f"member responsibility ${claim.amount:.2f}."
        )
        for claim in summary.recent_claims
    ]
    text = "\n".join(
        [
            f"Selected member name: {summary.name}.",
            f"Selected member age: {summary.age}.",
            f"Selected member plan: {summary.plan}.",
            (
                f"Deductible progress: ${summary.deductible.used:.0f} met of "
                f"${summary.deductible.total:.0f}."
            ),
            (
                f"Out-of-pocket progress: ${summary.oop.used:.0f} met of "
                f"${summary.oop.total:.0f}."
            ),
            "Loaded clinical conditions: "
            + (", ".join(summary.conditions) if summary.conditions else "none")
            + ".",
            "Mapped KB topics: "
            + (", ".join(summary.kb_topics) if summary.kb_topics else "none")
            + ".",
            "Medication topics inferred from profile: " + ", ".join(summary.medications) + ".",
            *topic_lines,
            *(claim_lines or ["Recent claims: none loaded."]),
        ]
    )
    return Hit(
        chunk_id="tool:member_profile",
        doc_id="tool:member_profile",
        source_type="tool",
        title="Selected member profile",
        source_url="",
        last_reviewed=None,
        section_path=None,
        text=text,
        score=1.0,
    )


def _fallback_profile_answer(question: str, hit: Hit, gateway: ModelGateway) -> TurnResult:
    answer = (
        "The selected member profile source does not show support for that profile claim. "
        f"{_PROFILE_CITATION}"
    )
    return _ok_result(
        question=question, answer=answer, citations=_citations([hit]), gateway=gateway
    )


def _profile_result(
    *,
    question: str,
    answer: str,
    hit: Hit,
    gateway: ModelGateway,
    source_hits: list[Hit] | None = None,
    rag_answers=None,
) -> TurnResult:
    return _ok_result(
        question=question,
        answer=answer,
        citations=_citations(source_hits or [hit]),
        gateway=gateway,
        rag_answers=rag_answers,
    )


def _member_plan_id(member_id: str) -> str | None:
    with session_scope() as session:
        return session.scalar(select(Member.plan_id).where(Member.member_id == member_id))


def _provider_search_for_member(question: str, plan_id: str | None) -> ProviderSearchOutput:
    specialty = specialty_hint(question)
    out = provider_search(
        ProviderSearchInput(
            specialty=specialty,
            plan_id=plan_id,
            accepting_new=True,
            limit=5,
        )
    )
    if not out.providers and specialty:
        out = provider_search(
            ProviderSearchInput(
                plan_id=plan_id,
                accepting_new=True,
                limit=5,
            )
        )
    return out


def _provider_recommendation_result(
    question: str,
    summary: MemberSummary,
    plan_id: str | None,
    gateway: ModelGateway,
) -> TurnResult:
    out = _provider_search_for_member(question, plan_id)
    specialty = specialty_hint(question)
    if not out.providers:
        return _escalated_result(question, "provider_search", gateway)

    fallback_note = ""
    if specialty and not any(
        specialty.lower() in (provider.specialty or "").lower() for provider in out.providers
    ):
        fallback_note = (
            f"I did not find accepting in-network {specialty.lower()} matches, so here are "
            "accepting in-network providers from the member's plan network instead.\n"
        )

    lines = []
    for provider in out.providers:
        location = ", ".join(part for part in (provider.city, provider.state) if part)
        status = (
            "accepting new patients"
            if provider.accepting_new
            else "not accepting new patients"
        )
        specialty_text = provider.specialty or "Provider"
        location_text = f" — {location}" if location else ""
        lines.append(f"- {provider.name} ({specialty_text}){location_text}; {status}.")

    answer = (
        f"{fallback_note}Recommended in-network providers for {summary.name.rstrip('.')}:\n"
        + "\n".join(lines)
    )
    citations = [
        Citation(f"tool:provider:{provider.npi}", provider.name, "", None)
        for provider in out.providers
    ]
    return _ok_result(
        question=question, answer=answer, citations=citations, gateway=gateway,
        intent="provider_search", tier_used="none",
    )


def _provider_detail_result(
    question: str,
    plan_id: str | None,
    gateway: ModelGateway,
) -> TurnResult | None:
    """Answer a 'tell me about <provider>' follow-up about a recommended provider.

    Returns None when the candidate name does not match an in-network provider, so the
    caller falls through to normal profile/KB handling instead of inventing an answer.
    """
    name = provider_detail_name(question)
    if not name:
        return None
    out = provider_lookup_by_name(name, plan_id)
    if not out.providers:
        return None

    provider = out.providers[0]
    location = ", ".join(part for part in (provider.city, provider.state) if part)
    status = (
        "is accepting new patients"
        if provider.accepting_new
        else "is not currently accepting new patients"
    )
    network = "in-network" if provider.in_network else "out-of-network"
    descriptor = f"{network} {provider.specialty}" if provider.specialty else f"{network} provider"
    article = "an" if descriptor[:1].lower() in "aeiou" else "a"
    location_text = f" in {location}" if location else ""
    answer = (
        f"{provider.name} is {article} {descriptor}{location_text} and {status}."
    )
    citations = [Citation(f"tool:provider:{provider.npi}", provider.name, "", None)]
    return _ok_result(
        question=question, answer=answer, citations=citations, gateway=gateway,
        intent="provider_search", tier_used="none",
    )


@dataclass(frozen=True)
class _MedicationRisk:
    """A medication-specific safety signal the profile can surface, driven by data not code.

    Adding a drug is a new entry here, not new branches in _risk_answer.
    """

    medication: str            # substring matched against summary.medications (lowercased)
    augment: str               # extra retrieval terms to find the right label chunk
    doc_marker: str            # substring identifying the drug in a retrieved hit's doc_id
    text_marker: str           # substring confirming the hit is the relevant warning
    aggravating_topic: str     # KB topic that raises the risk (e.g. "chronic kidney disease")
    factor_label: str          # how the med is described ("inferred Metformin use")
    aggravating_label: str     # how the topic is described ("a Chronic Kidney Disease signal")
    warning: str               # the grounded warning sentences (the {cite} placeholder filled)


_MEDICATION_RISKS: tuple[_MedicationRisk, ...] = (
    _MedicationRisk(
        medication="metformin",
        augment="metformin lactic acidosis kidney impairment",
        doc_marker="metformin",
        text_marker="lactic acidosis",
        aggravating_topic="chronic kidney disease",
        factor_label="inferred Metformin use",
        aggravating_label="a Chronic Kidney Disease profile signal",
        warning=(
            "Metformin carries a boxed warning for rare but serious lactic acidosis, and "
            "risk is higher with kidney impairment. {cite} The label also says kidney "
            "function is checked before and during treatment, and to seek care for symptoms "
            "such as unusual muscle pain, trouble breathing, unusual sleepiness, or severe "
            "stomach pain. {cite}"
        ),
    ),
)


def _matching_risk(summary: MemberSummary) -> _MedicationRisk | None:
    """The first known medication-risk whose drug appears in the member's medications.

    Returns None when the member is on none of the risk medications — callers must NOT
    fabricate a warning for a drug the member isn't taking.
    """
    meds = [m.lower() for m in summary.medications]
    for risk in _MEDICATION_RISKS:
        if any(risk.medication in m for m in meds):
            return risk
    return None


def _risk_answer(
    question: str,
    summary: MemberSummary,
    hit: Hit,
    gateway: ModelGateway,
    citation: str,
    topics: str,
) -> TurnResult:
    name = summary.name.rstrip(".")
    risk = _matching_risk(summary)

    # No medication-specific risk applies to this member's actual medications. Answer from
    # their real profile rather than warning about a drug they are not taking.
    if risk is None:
        meds = ", ".join(summary.medications) if summary.medications else "no medications"
        answer = (
            f"I don't see a specific medication-safety risk to flag for {name} from the "
            f"selected profile. Active medications are {meds}, and the visible KB topics "
            f"are: {topics}. For a clinical risk assessment, a care manager should review "
            f"the full record. {citation}"
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    medication_hits = retrieval.retrieve(
        f"{question} {risk.augment}", intent="medication", k=3, gateway=gateway
    )
    label_hit = next(
        (
            candidate
            for candidate in medication_hits
            if risk.doc_marker in candidate.doc_id.lower()
            and risk.text_marker in candidate.text.lower()
        ),
        None,
    )
    has_aggravating = any(t.lower() == risk.aggravating_topic for t in summary.kb_topics)
    profile_factors = [risk.factor_label]
    if has_aggravating:
        profile_factors.append(risk.aggravating_label)

    if label_hit:
        risk_word = "does" if has_aggravating else "may"
        warning = risk.warning.format(cite=format_citation(label_hit.chunk_id))
        answer = (
            f"{name} {risk_word} have a medication risk signal to review: the selected "
            f"profile includes {', '.join(profile_factors)}. {citation} {warning}"
        )
        return _profile_result(
            question=question, answer=answer, hit=hit, gateway=gateway,
            source_hits=[hit, label_hit],
        )

    answer = (
        f"{name}'s selected profile includes {', '.join(profile_factors)}, but I could "
        f"not retrieve a medication-label source for the risk mechanism. {citation}"
    )
    return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)


def _summary_answer(name: str, summary: MemberSummary, topics: str, conditions: str) -> str:
    return (
        f"{name} is a {summary.age}-year-old synthetic Synthea member on {summary.plan}. "
        f"The selected profile maps to these KB topics: {topics}. "
        f"Deductible progress is ${summary.deductible.used:.0f} of "
        f"${summary.deductible.total:.0f}, and out-of-pocket progress is "
        f"${summary.oop.used:.0f} of ${summary.oop.total:.0f}. {_PROFILE_CITATION}"
    )


def _conditions_answer(name: str, summary: MemberSummary, topics: str, conditions: str) -> str:
    return (
        f"{name}'s loaded clinical conditions include: {conditions}. "
        f"The selected profile maps to these KB topics: {topics}. {_PROFILE_CITATION}"
    )


def _coverage_answer(name: str, summary: MemberSummary, topics: str, conditions: str) -> str:
    deductible_remaining = max(summary.deductible.total - summary.deductible.used, 0.0)
    oop_remaining = max(summary.oop.total - summary.oop.used, 0.0)
    return (
        f"{name} is enrolled in {summary.plan}. Deductible progress is "
        f"${summary.deductible.used:.0f} of ${summary.deductible.total:.0f}, "
        f"so ${deductible_remaining:.0f} remains. "
        f"Out-of-pocket progress is ${summary.oop.used:.0f} of "
        f"${summary.oop.total:.0f}, so ${oop_remaining:.0f} remains. {_PROFILE_CITATION}"
    )


def _claims_answer(name: str, summary: MemberSummary, topics: str, conditions: str) -> str:
    if summary.recent_claims:
        claims = "; ".join(
            f"{claim.description} ({claim.status}), member responsibility "
            f"${claim.amount:.2f}"
            for claim in summary.recent_claims
        )
        return f"{name}'s recent claims are: {claims}. {_PROFILE_CITATION}"
    return f"{name} has no recent claims loaded in this selected profile. {_PROFILE_CITATION}"


def _medications_answer(name: str, summary: MemberSummary, topics: str, conditions: str) -> str:
    return (
        f"Medication topics inferred from {name}'s selected profile are: "
        f"{', '.join(summary.medications)}. {_PROFILE_CITATION}"
    )


# kind -> text builder, for the slots that produce a plain string from the profile facts.
# risk and specific_condition need extra context (retrieval / topic resolution) and are
# handled out of band in _answer_profile_slot.
_SLOT_ANSWERS = {
    "summary": _summary_answer,
    "conditions": _conditions_answer,
    "coverage": _coverage_answer,
    "claims": _claims_answer,
    "medications": _medications_answer,
}


def _specific_condition_answer(
    question: str, summary: MemberSummary, analysis: QueryAnalysis, gateway: ModelGateway,
    name: str, topics: str, conditions: str,
) -> str:
    # Resolve the asked-about condition to a canonical topic. The analyzer slot is
    # unreliable here — it has returned None ("does hilton have cancer") or a raw, unmapped
    # word ("tumor"); resolve_condition_topic only trusts a value that maps to a real topic,
    # then falls back to an LLM extractor (synonyms like "sugar") and a deterministic
    # matcher, so a missing/garbled slot never becomes a false "No".
    resolved = resolve_condition_topic(question, analysis.condition_topic, gateway)
    asked = resolved or "that condition"
    matched = {topic.lower(): topic for topic in summary.kb_topics}.get(asked.lower())
    if matched:
        return (
            f"Yes. {name}'s selected profile has a {matched} profile signal. "
            f"Loaded clinical conditions include: {conditions}. {_PROFILE_CITATION}"
        )
    return (
        f"No loaded {asked} profile signal appears for {name}. "
        f"The visible KB topics are: {topics}. {_PROFILE_CITATION}"
    )


def _answer_profile_slot(
    question: str, summary: MemberSummary, analysis: QueryAnalysis, hit: Hit, gateway: ModelGateway
) -> TurnResult | None:
    name = summary.name.rstrip(".")
    topics = ", ".join(summary.kb_topics) if summary.kb_topics else "none"
    conditions = (
        ", ".join(summary.conditions) if summary.conditions else "no loaded clinical conditions"
    )

    builder = _SLOT_ANSWERS.get(analysis.kind)
    if builder:
        answer = builder(name, summary, topics, conditions)
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if analysis.kind == "risk":
        return _risk_answer(question, summary, hit, gateway, _PROFILE_CITATION, topics)

    if analysis.kind == "specific_condition":
        answer = _specific_condition_answer(
            question, summary, analysis, gateway, name, topics, conditions
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    return None


def profile_turn(
    question: str, member_ref: str | None, member_id_hint: str | None, gateway: ModelGateway
) -> TurnResult | None:
    member_id = resolve_member_ref(member_ref) or member_id_hint
    if not member_id:
        return None

    summary = load_member_summary(member_id)
    if not summary:
        return None

    hit = _profile_hit(summary)
    analysis = analyze_member_query(question, summary, gateway)
    if not analysis.needs_profile:
        return None
    if analysis.kind == "provider_search":
        return _provider_recommendation_result(
            question, summary, _member_plan_id(member_id), gateway
        )
    if analysis.kind == "provider_detail":
        # On no match, fall through to None so the general orchestrator handles it as a
        # normal "tell me about X" question instead of escalating from the profile path.
        return _provider_detail_result(question, _member_plan_id(member_id), gateway)

    slotted = _answer_profile_slot(question, summary, analysis, hit, gateway)
    if slotted:
        return slotted
    if analysis.kind == "other":
        return _fallback_profile_answer(question, hit, gateway)

    answer = generate_grounded(question, [hit], gateway=gateway, retrieval_conf=1.0)
    if not answer.grounded or not answer.citations:
        return _fallback_profile_answer(question, hit, gateway)
    return _profile_result(
        question=question,
        answer=answer.answer,
        hit=hit,
        gateway=gateway,
        rag_answers=[answer],
    )

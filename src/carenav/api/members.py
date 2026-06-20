"""Synthea member presentation helpers for the API."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from carenav.agents import create_demo_member_ref
from carenav.agents.contracts import ProviderSearchInput
from carenav.agents.providers import provider_search
from carenav.api.member_content import (
    HIGH_SIGNAL_TOPICS,
    MEDICATIONS_BY_TOPIC,
    NO_MEDICATIONS,
    SPECIALTY_BY_TOPIC,
    SUGGESTED_QUESTIONS_BY_TOPIC,
)
from carenav.api.schemas import MemberSummary, SuggestedQuestion
from carenav.data import condition_topics
from carenav.data.db import session_scope
from carenav.data.models import Condition, Member, Plan


def age(dob: date) -> int:
    today = date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def topic_label(topic: str) -> str:
    return topic.replace("-", " ").title()


def condition_priority(condition: Condition) -> bool:
    return condition.kb_topic is not None and condition_topics.is_clinical(condition.display)


def clinical_conditions(member: Member) -> list[Condition]:
    active = [
        c
        for c in member.conditions
        if condition_priority(c) and c.clinical_status == "active"
    ]
    inactive = [
        c
        for c in member.conditions
        if condition_priority(c) and c.clinical_status != "active"
    ]
    return sorted(active, key=lambda c: c.onset_date or date.min, reverse=True) + sorted(
        inactive, key=lambda c: c.onset_date or date.min, reverse=True
    )


def condition_topics_for(member: Member) -> list[str]:
    topics: list[str] = []
    for condition in clinical_conditions(member):
        if condition.kb_topic and condition.kb_topic not in topics:
            topics.append(condition.kb_topic)
    return topics


def medications_for_topics(topics: list[str]) -> list[str]:
    """Union of the medications mapped to each topic (deduped, order-preserving)."""
    meds: list[str] = []
    for topic in topics:
        for med in MEDICATIONS_BY_TOPIC.get(topic, []):
            if med not in meds:
                meds.append(med)
    return meds or [NO_MEDICATIONS]


def provider_specialty_for_topics(topics: list[str]) -> str | None:
    """Recommended specialty for the first of the member's topics that maps to one."""
    for topic in topics:
        if topic in SPECIALTY_BY_TOPIC:
            return SPECIALTY_BY_TOPIC[topic]
    return None


def provider_recommendations(
    plan_id: str | None, topics: list[str], limit: int = 2, session=None
) -> list[dict]:
    if not plan_id:
        return []
    specialty = provider_specialty_for_topics(topics)
    out = provider_search(
        ProviderSearchInput(
            plan_id=plan_id,
            specialty=specialty,
            accepting_new=True,
            limit=limit,
        ),
        session=session,
    )
    if not out.providers and specialty:
        out = provider_search(
            ProviderSearchInput(plan_id=plan_id, accepting_new=True, limit=limit),
            session=session,
        )
    return [
        {
            "name": provider.name,
            "specialty": provider.specialty or "Provider",
        }
        for provider in out.providers
    ]


def display_name(name: str, fallback: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return fallback
    first = "".join(ch for ch in parts[0] if ch.isalpha()) or parts[0]
    last = "".join(ch for ch in parts[-1] if ch.isalpha()) if len(parts) > 1 else ""
    return f"{first} {last[:1]}." if last else first


def member_summary(member: Member, index: int = 0) -> MemberSummary:
    plan = member.plan
    latest_acc = sorted(member.accumulators, key=lambda acc: acc.plan_year, reverse=True)
    acc = latest_acc[0] if latest_acc else None
    claims = sorted(member.claims, key=lambda claim: claim.claim_id, reverse=True)[:3]
    clinical = clinical_conditions(member)
    conditions = [c.display for c in clinical[:5]]
    topics = condition_topics_for(member)[:5]
    meds = medications_for_topics(topics)
    plan_name = plan.name if plan else member.plan_id
    summary_bits = [topic_label(topic) for topic in topics[:2]] or ["benefits questions"]
    if claims:
        summary_bits.append("recent claims")
    return MemberSummary(
        id=member.member_id,
        name=display_name(member.name, f"Member {index + 1}"),
        age=age(member.dob),
        plan=plan_name,
        summary=", ".join(summary_bits),
        member_ref=create_demo_member_ref(member.member_id),
        plan_type=f"{plan_name} - synthetic demo member",
        deductible={
            "used": float(acc.deductible_met) if acc else 0.0,
            "total": float(plan.deductible) if plan else 0.0,
        },
        oop={
            "used": float(acc.oop_met) if acc else 0.0,
            "total": float(plan.oop_max) if plan else 0.0,
        },
        medications=meds,
        conditions=conditions,
        kb_topics=[topic_label(topic) for topic in topics],
        recent_claims=[
            {
                "description": f"Service code {claim.service_code}",
                "date": claim.claim_id[-10:] if len(claim.claim_id) >= 10 else claim.claim_id,
                "amount": float(claim.member_responsibility),
                "status": claim.status.title(),
            }
            for claim in claims
        ],
        # Provider recommendations are fetched lazily per selected member via
        # /members/{id}/providers — computing them for every row makes the list hang.
        recent_providers=[],
        note="Synthetic demo member. "
        + (
            "Active conditions: " + ", ".join(conditions) + "."
            if conditions
            else "No active condition summary loaded."
        ),
    )


# Demo-ranking weights: an adult with several high-signal conditions and some claims makes
# a more interesting profile to demo than a young member with none.
_ADULT_BONUS = 10
_PER_TOPIC = 3
_HIGH_SIGNAL_BONUS = 5
_MAX_CLAIM_BONUS = 5


def demo_score(member: Member) -> int:
    score = 0
    if age(member.dob) >= 18:
        score += _ADULT_BONUS
    topics = condition_topics_for(member)
    score += len(topics) * _PER_TOPIC
    score += sum(_HIGH_SIGNAL_BONUS for topic in topics if topic in HIGH_SIGNAL_TOPICS)
    score += min(len(member.claims), _MAX_CLAIM_BONUS)
    return score


def sort_synthea_members(rows: list[Member]) -> list[Member]:
    """Return all Synthea members, with richer demo profiles first."""
    return sorted(rows, key=lambda member: (demo_score(member), member.member_id), reverse=True)


def list_member_summaries() -> list[MemberSummary]:
    with session_scope() as session:
        rows = (
            session.execute(
                select(Member)
                .options(
                    selectinload(Member.plan),
                    selectinload(Member.accumulators),
                    selectinload(Member.claims),
                    selectinload(Member.conditions),
                )
                .join(Plan)
                .order_by(Member.member_id)
            )
            .scalars()
            .all()
        )
        rows = sort_synthea_members(rows)
        return [member_summary(member, i) for i, member in enumerate(rows)]


def load_member_summary(member_id: str) -> MemberSummary | None:
    with session_scope() as session:
        member = session.get(
            Member,
            member_id,
            options=[
                selectinload(Member.plan),
                selectinload(Member.accumulators),
                selectinload(Member.claims),
                selectinload(Member.conditions),
            ],
        )
        return member_summary(member, 0) if member else None


def provider_recommendations_for_member(member_id: str) -> list[dict]:
    """Recommended in-network providers for one selected member.

    Fetched lazily by the UI on member-select (like suggested questions) so the bulk
    /members list stays fast — computing recommendations for all members per list load
    issues a provider query per row and hangs the request.
    """
    with session_scope() as session:
        member = session.get(
            Member, member_id, options=[selectinload(Member.conditions)]
        )
        if not member:
            return []
        topics = condition_topics_for(member)
        return provider_recommendations(member.plan_id, topics, session=session)


def topic_questions(conditions: list[Condition], topics: list[str]) -> list[SuggestedQuestion]:
    questions: list[SuggestedQuestion] = []
    primary = conditions[0].display if conditions else None

    for topic in topics:
        questions.extend(SUGGESTED_QUESTIONS_BY_TOPIC.get(topic, []))

    if primary and not questions:
        questions.append(
            SuggestedQuestion(
                label=topic_label(topics[0]) if topics else "Condition info",
                question=f"What should I know about {primary}?",
                intent="condition_info",
            )
        )
    if primary:
        questions.append(
            SuggestedQuestion(
                label="Care coverage",
                question=f"What care for {primary} is covered under my plan?",
                intent="benefits",
            )
        )

    deduped: list[SuggestedQuestion] = []
    seen: set[str] = set()
    for question in questions:
        if question.question not in seen:
            deduped.append(question)
            seen.add(question.question)
    return deduped


def suggested_questions_for_member(member_id: str) -> list[SuggestedQuestion]:
    with session_scope() as session:
        member = session.get(
            Member,
            member_id,
            options=[
                selectinload(Member.plan),
                selectinload(Member.conditions),
                selectinload(Member.claims),
            ],
        )
        if not member:
            return []
        clinical = clinical_conditions(member)
        topics = condition_topics_for(member)[:5]
        claims = sorted(member.claims, key=lambda claim: claim.claim_id, reverse=True)
        out = [
            SuggestedQuestion(
                label="Profile summary",
                question="Summarize this member's profile.",
                intent="member_profile",
            ),
            SuggestedQuestion(
                label="Deductible status",
                question="Have I met my deductible, and how much is left?",
                intent="benefits",
            ),
        ]
        out.extend(topic_questions(clinical, topics))
        if claims:
            out.append(
                SuggestedQuestion(
                    label="Explain last claim",
                    question="Can you explain my most recent claim and why I owed money?",
                    intent="claims",
                )
            )
        out.extend(
            [
                SuggestedQuestion(
                    label="Find provider",
                    question="Find an in-network specialist near me.",
                    intent="providers",
                ),
                SuggestedQuestion(
                    label="Emergency test",
                    question="I have chest pain right now, what should I do?",
                    intent="safety",
                ),
            ]
        )
        return out[:5]

"""Selected-member profile answering for the API."""

from __future__ import annotations

from carenav.agents import resolve_member_ref
from carenav.api.members import load_member_summary, topic_label
from carenav.api.query_analyzer import QueryAnalysis, analyze_member_query
from carenav.api.schemas import MemberSummary
from carenav.data import condition_topics
from carenav.models import ModelGateway
from carenav.orchestrator.state import ConfidenceBreakdown, TurnResult
from carenav.rag import retrieval
from carenav.rag.agent import Citation, generate_grounded
from carenav.rag.retrieval import Hit


def _profile_hit(summary: MemberSummary) -> Hit:
    present_topics = set(summary.kb_topics)
    topic_lines = [
        f"{topic_label(topic)} profile signal: "
        f"{'present' if topic_label(topic) in present_topics else 'absent'}."
        for topic in condition_topics.TOPICS
    ]
    claim_lines = [
        (
            f"Recent claim: {claim['description']}; status {claim['status']}; "
            f"member responsibility ${claim['amount']:.2f}."
        )
        for claim in summary.recent_claims
    ]
    text = "\n".join(
        [
            f"Selected member name: {summary.name}.",
            f"Selected member age: {summary.age}.",
            f"Selected member plan: {summary.plan}.",
            (
                f"Deductible progress: ${summary.deductible['used']:.0f} met of "
                f"${summary.deductible['total']:.0f}."
            ),
            (
                f"Out-of-pocket progress: ${summary.oop['used']:.0f} met of "
                f"${summary.oop['total']:.0f}."
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
        "[CHUNK:tool:member_profile]"
    )
    return TurnResult(
        question=question,
        intent="member_profile",
        sub_questions=[question],
        answer=answer,
        citations=[Citation(hit.chunk_id, hit.title, hit.source_url, hit.section_path)],
        grounded=True,
        escalated=False,
        handoff=None,
        confidence=ConfidenceBreakdown(
            intent_conf=1.0, retrieval_conf=1.0, tool_conf=1.0, self_eval=1.0
        ),
        tier_used="small",
        safety_flag="none",
        cost_usd=gateway.ledger.total_cost_usd,
        rag_answers=[],
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
    hits = source_hits or [hit]
    return TurnResult(
        question=question,
        intent="member_profile",
        sub_questions=[question],
        answer=answer,
        citations=[Citation(h.chunk_id, h.title, h.source_url, h.section_path) for h in hits],
        grounded=True,
        escalated=False,
        handoff=None,
        confidence=ConfidenceBreakdown(
            intent_conf=1.0, retrieval_conf=1.0, tool_conf=1.0, self_eval=1.0
        ),
        tier_used="small",
        safety_flag="none",
        cost_usd=gateway.ledger.total_cost_usd,
        rag_answers=rag_answers or [],
    )


def _risk_answer(
    question: str,
    summary: MemberSummary,
    hit: Hit,
    gateway: ModelGateway,
    citation: str,
    topics: str,
) -> TurnResult:
    medication_hits = retrieval.retrieve(
        question + " metformin lactic acidosis kidney impairment",
        intent="medication",
        k=3,
        gateway=gateway,
    )
    metformin_hit = next(
        (
            candidate
            for candidate in medication_hits
            if "metformin" in candidate.doc_id.lower()
            and "lactic acidosis" in candidate.text.lower()
        ),
        None,
    )
    has_metformin = any("metformin" in medication.lower() for medication in summary.medications)
    has_ckd = any(topic.lower() == "chronic kidney disease" for topic in summary.kb_topics)
    profile_factors = []
    if has_metformin:
        profile_factors.append("inferred Metformin use")
    if has_ckd:
        profile_factors.append("a Chronic Kidney Disease profile signal")
    if not profile_factors:
        profile_factors.append(f"these visible KB topics: {topics}")

    name = summary.name.rstrip(".")
    if metformin_hit:
        risk_word = "does" if has_metformin and has_ckd else "may"
        answer = (
            f"{name} {risk_word} have a metformin-related lactic acidosis risk signal "
            f"to review: the selected profile includes {', '.join(profile_factors)}. "
            f"{citation} Metformin carries a boxed warning for rare but serious lactic "
            f"acidosis, and risk is higher with kidney impairment. "
            f"[CHUNK:{metformin_hit.chunk_id}] The label also says kidney function is "
            f"checked before and during treatment, and to seek care for symptoms such as "
            f"unusual muscle pain, trouble breathing, unusual sleepiness, or severe "
            f"stomach pain. [CHUNK:{metformin_hit.chunk_id}]"
        )
        return _profile_result(
            question=question,
            answer=answer,
            hit=hit,
            gateway=gateway,
            source_hits=[hit, metformin_hit],
        )

    answer = (
        f"{name}'s selected profile includes {', '.join(profile_factors)}, but I could "
        f"not retrieve a medication-label source for the risk mechanism. {citation}"
    )
    return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)


def _answer_profile_slot(
    question: str, summary: MemberSummary, analysis: QueryAnalysis, hit: Hit, gateway: ModelGateway
) -> TurnResult | None:
    query_type = analysis.kind
    name = summary.name.rstrip(".")
    citation = "[CHUNK:tool:member_profile]"
    topics = ", ".join(summary.kb_topics) if summary.kb_topics else "none"
    conditions = (
        ", ".join(summary.conditions) if summary.conditions else "no loaded clinical conditions"
    )

    if query_type == "summary":
        answer = (
            f"{name} is a {summary.age}-year-old synthetic Synthea member on {summary.plan}. "
            f"The selected profile maps to these KB topics: {topics}. "
            f"Deductible progress is ${summary.deductible['used']:.0f} of "
            f"${summary.deductible['total']:.0f}, and out-of-pocket progress is "
            f"${summary.oop['used']:.0f} of ${summary.oop['total']:.0f}. {citation}"
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if query_type == "conditions":
        answer = (
            f"{name}'s loaded clinical conditions include: {conditions}. "
            f"The selected profile maps to these KB topics: {topics}. {citation}"
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if query_type == "coverage":
        deductible_remaining = max(
            summary.deductible["total"] - summary.deductible["used"], 0.0
        )
        oop_remaining = max(summary.oop["total"] - summary.oop["used"], 0.0)
        answer = (
            f"{name} is enrolled in {summary.plan}. Deductible progress is "
            f"${summary.deductible['used']:.0f} of ${summary.deductible['total']:.0f}, "
            f"so ${deductible_remaining:.0f} remains. "
            f"Out-of-pocket progress is ${summary.oop['used']:.0f} of "
            f"${summary.oop['total']:.0f}, so ${oop_remaining:.0f} remains. {citation}"
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if query_type == "claims":
        if summary.recent_claims:
            claims = "; ".join(
                f"{claim['description']} ({claim['status']}), member responsibility "
                f"${claim['amount']:.2f}"
                for claim in summary.recent_claims
            )
            answer = f"{name}'s recent claims are: {claims}. {citation}"
        else:
            answer = f"{name} has no recent claims loaded in this selected profile. {citation}"
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if query_type == "medications":
        answer = (
            f"Medication topics inferred from {name}'s selected profile are: "
            f"{', '.join(summary.medications)}. {citation}"
        )
        return _profile_result(question=question, answer=answer, hit=hit, gateway=gateway)

    if query_type == "risk":
        return _risk_answer(question, summary, hit, gateway, citation, topics)

    if query_type == "specific_condition":
        asked = str(analysis.condition_topic or "that condition").strip()
        visible = {topic.lower(): topic for topic in summary.kb_topics}
        matched = visible.get(asked.lower())
        if matched:
            answer = (
                f"Yes. {name}'s selected profile has a {matched} profile signal. "
                f"Loaded clinical conditions include: {conditions}. {citation}"
            )
        else:
            answer = (
                f"No loaded {asked} profile signal appears for {name}. "
                f"The visible KB topics are: {topics}. {citation}"
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

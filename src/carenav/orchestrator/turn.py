"""run_turn — the orchestrator turn pipeline (docs/03, docs/06): route → (decompose) →
plan → tool_exec → reflect → generate (grounded) → verify → respond | escalate.

Plain typed Python, one function per node, names matching docs/03 so adopting a graph
framework later (for the redact node, persistent sessions) stays mechanical. Policy per
docs/06:

  * emergent triage short-circuits to a human handoff — no model can contain it;
  * specialist tools (member/benefit/claims/provider) run for turns that need member
    context; their structured outputs become groundable sources cited like KB chunks;
  * KB intents answer via the RAG agent (per-sub-question when decomposed); a turn can
    combine tool sources AND KB chunks (e.g. "did I meet my deductible and is an MRI
    covered?" → member_account + benefit_lookup, grounded together);
  * a verify pass checks cited docs match the question's subject (fail → escalate);
  * composite confidence (incl. tool_conf from agent completeness) is scored against
    tau_high (urgent) / tau_low; ONE frontier retry on a miss; then human handoff.
"""

from __future__ import annotations

from dataclasses import replace

from carenav.agents import (
    ProviderSearchInput,
    member_phi_values,
    provider_search,
    specialty_hint,
)
from carenav.config import settings
from carenav.models import ModelGateway
from carenav.orchestrator import contextualize as _contextualize
from carenav.orchestrator import decompose as _decompose
from carenav.orchestrator import router as _router
from carenav.orchestrator import tools as _tools
from carenav.orchestrator import verify as _verify
from carenav.orchestrator.state import (
    KB_INTENTS,
    SAFETY_INTENT,
    ConfidenceBreakdown,
    HandoffPacket,
    TierAttempt,
    TurnResult,
)
from carenav.rag import retrieval
from carenav.rag.agent import Citation, RagAnswer, answer_question, generate_grounded
from carenav.rag.retrieval import Hit, retrieval_conf
from carenav.redaction import PiiMap, redact, rehydrate


def _handoff(question, intent, answers, reason, safety) -> HandoffPacket:
    gathered = [c.chunk_id for a in answers for c in a.citations]
    return HandoffPacket(
        redacted_summary=question,  # redaction layer tokenizes this upstream
        suspected_intent=intent,
        gathered=gathered,
        reason=reason,
        safety_flag=safety,
    )


def _escalate(question, intent, subs, answers, conf, reason, safety, tier, cost,
              tools_run=None, tier_attempts=None) -> TurnResult:
    return TurnResult(
        question=question, intent=intent, sub_questions=subs, answer="",
        citations=[], grounded=False, escalated=True,
        handoff=_handoff(question, intent, answers, reason, safety),
        confidence=conf, tier_used=tier, safety_flag=safety, cost_usd=cost,
        rag_answers=answers,
        tools_run=tools_run or [], tier_attempts=tier_attempts or [],
    )


def _redact_sources(
    sources: list[Hit], pii_map: PiiMap, gw: ModelGateway,
    known_values: dict[str, str] | None = None,
) -> None:
    """Redact PII in each tool-output source's text in place (docs/05).

    Tool facts can carry member PHI (names, etc.); they must be tokenized before reaching
    the generator or re-entering graph state. Hit is frozen, so we swap in a redacted copy.
    Reuses the turn's pii_map so tokens are consistent with the redacted question.
    ``known_values`` feeds the deterministic field layer with the resolved member's record.
    """
    for i, hit in enumerate(sources):
        if not hit.text:
            continue
        redacted, _ = redact(
            hit.text, pii_map, known_values=known_values, gateway=gw, source="tool_output"
        )
        if redacted != hit.text:
            sources[i] = replace(hit, text=redacted)


def _answer_subs(
    subs: list[str], intent: str | None, gateway: ModelGateway, model: str | None
) -> list[RagAnswer]:
    return [answer_question(s, intent=intent, gateway=gateway, model=model) for s in subs]


def _merge(answers: list[RagAnswer]) -> tuple[str, list, bool]:
    """Combine per-sub-question answers; grounded only if every part grounded."""
    grounded = all(a.grounded for a in answers) and bool(answers)
    text = "\n\n".join(a.answer for a in answers if a.answer)
    citations, seen = [], set()
    for a in answers:
        for c in a.citations:
            if c.chunk_id not in seen:
                seen.add(c.chunk_id)
                citations.append(c)
    return text, citations, grounded


def _confidence(
    intent_conf: float, answers: list[RagAnswer], grounded: bool, tool_conf: float = 1.0
) -> ConfidenceBreakdown:
    retrieval = min((a.retrieval_conf for a in answers), default=0.0)
    return ConfidenceBreakdown(
        intent_conf=intent_conf,
        retrieval_conf=retrieval,
        tool_conf=tool_conf,
        self_eval=1.0 if grounded else 0.0,  # groundedness as the self-evaluation proxy
    )


def run_turn(
    question: str,
    member_ref: str | None = None,
    gateway: ModelGateway | None = None,
    history: list[_contextualize.Turn] | None = None,
) -> TurnResult:
    """Run one member turn through the orchestrator. Never guesses: escalates instead.

    `member_ref` is the opaque session reference; the agent layer resolves it to a real
    member_id (carenav.agents.session). Turns needing member context but lacking a ref
    escalate rather than guess.

    `history` is the prior conversation (oldest first). When present, a follow-up question
    is first rewritten to stand on its own ("what are the side effects?" after "what is
    albuterol?" → "what are albuterol's side effects?") so routing and retrieval have a
    complete subject. Fails open to the original question.
    """
    gw = gateway or ModelGateway()

    # --- contextualize: resolve a follow-up into a standalone question using prior turns,
    # BEFORE redaction/routing, so every downstream node sees a self-contained subject.
    question = _contextualize.contextualize_question(question, history, gw)

    # --- redact (docs/05): tokenize PII in the user's text BEFORE any model call ---
    # Everything downstream (router, plan, decompose, generate, verify, handoff) operates on
    # the REDACTED question, so no raw PHI ever reaches a model prompt or the graph state.
    # The reversible pii_map is held here (out of band) for the single rehydrate at the end.
    # Safety triage is unaffected: redaction targets identifiers, not symptoms.
    # An authenticated member's known record values (name/dob/address/id) feed the
    # deterministic field layer — caught with certainty even if the model layer is offline.
    pii_map = PiiMap()
    known_phi = member_phi_values(member_ref)
    question, _audit = redact(
        question, pii_map, known_values=known_phi, gateway=gw, source="user_text"
    )

    # --- route (safety triage + intent) ---
    intent, intent_conf, safety = _router.route(question, gw)

    # A paraphrased emergency can slip past the regex triage but still be caught by the
    # LLM classifier ("emergency" intent). Treat it as emergent either way — the
    # missed-escalation hard gate (docs/09) says a false positive is acceptable; a miss
    # is not.
    if intent == SAFETY_INTENT:
        safety = "emergent"

    def escalate_unanswered(reason: str, conf: ConfidenceBreakdown) -> TurnResult:
        # Escalate before any answer exists (no sub-questions/answers gathered yet).
        return _escalate(question, intent, [question], [], conf, reason, safety,
                         "human", gw.ledger.total_cost_usd)

    if safety == "emergent":
        return escalate_unanswered("emergent_safety", ConfidenceBreakdown(intent_conf=1.0))

    if intent == "out_of_scope":
        return escalate_unanswered("out_of_scope", ConfidenceBreakdown(intent_conf=intent_conf))

    if intent == "provider_search":
        return _provider_turn(question, intent, intent_conf, safety, gw)

    kb_intent = intent if intent in KB_INTENTS else None

    # --- plan → tool_exec → reflect: run specialist tools the turn needs ---
    plan = _tools.plan_tools(question, intent)
    tool_run = _tools.ToolRun()
    if plan.needs_member or plan.needs_benefit or plan.needs_claims:
        # The turn needs member data; escalate rather than fabricate if we can't resolve it.
        if member_ref is None:
            return escalate_unanswered(
                "member_context_required", ConfidenceBreakdown(intent_conf=intent_conf)
            )
        tool_run = _tools.exec_and_reflect(question, member_ref, plan, gw)
        if not tool_run.member_id_resolved:
            return escalate_unanswered(
                "member_context_required", ConfidenceBreakdown(intent_conf=intent_conf)
            )
        # Redact tool-output PII BEFORE it re-enters state / reaches the generator (docs/05).
        # Reuse the turn's pii_map so a value tokenized in the question keeps the same token.
        _redact_sources(tool_run.sources, pii_map, gw, known_values=known_phi)

    # --- decompose (comparatives → per-subject sub-questions) ---
    subs = _decompose.decompose(question, gw)

    bar = settings.tau_high if safety == "urgent" else settings.tau_low
    tools_run = list(tool_run.outputs.keys())

    # Try the small tier, then escalate to frontier only if it misses the confidence bar.
    answers, text, citations, grounded, conf, tier, attempts = _answer_at_tiers(
        question, subs, kb_intent, tool_run, intent_conf, bar, gw
    )
    if conf.weighted_sum() < bar:
        return _escalate(question, intent, subs, answers, conf,
                         "low_conf_high_stakes" if safety == "urgent" else "groundedness_fail",
                         safety, "human", gw.ledger.total_cost_usd,
                         tools_run=tools_run, tier_attempts=attempts)

    # --- verify cited docs match the question's subject (fail safe) ---
    if not _verify.verify_citations(question, answers, gw):
        return _escalate(question, intent, subs, answers, conf,
                         "verify_fail", safety, "human", gw.ledger.total_cost_usd,
                         tools_run=tools_run, tier_attempts=attempts)

    # --- rehydrate (docs/05): the ONLY point tokens → real values, on the user-facing
    # string only. Graph state / citations / handoff keep the tokenized form.
    answer = rehydrate(text, pii_map)

    return TurnResult(
        question=question, intent=intent, sub_questions=subs, answer=answer,
        citations=citations, grounded=grounded, escalated=False, handoff=None,
        confidence=conf, tier_used=tier, safety_flag=safety,
        cost_usd=gw.ledger.total_cost_usd, rag_answers=answers,
        tools_run=tools_run, tier_attempts=attempts,
    )


def _answer_at_tiers(
    question: str,
    subs: list[str],
    kb_intent: str | None,
    tool_run: _tools.ToolRun,
    intent_conf: float,
    bar: float,
    gw: ModelGateway,
) -> tuple[list[RagAnswer], str, list, bool, ConfidenceBreakdown, str, list[TierAttempt]]:
    """Answer at the small tier, retry once at the frontier tier if it misses `bar`.

    Returns the best attempt's (answers, text, citations, grounded, confidence, tier_used)
    plus a TierAttempt per tier tried (eval telemetry — lets the harness replay the tau
    selection rule offline). The caller compares confidence against `bar` to decide answer
    vs escalate, so this never raises — it just returns the frontier attempt when the small
    tier falls short.
    """
    result: tuple[list[RagAnswer], str, list, bool, ConfidenceBreakdown, str] | None = None
    attempts: list[TierAttempt] = []
    for tier, model in (("small", None), ("frontier", settings.model_frontier)):
        cost_before = gw.ledger.total_cost_usd
        answers = _answer_turn(
            question, subs, kb_intent, tool_run.sources, gw, model, plan_id=tool_run.plan_id
        )
        text, citations, grounded = _merge(answers)
        conf = _confidence(intent_conf, answers, grounded, tool_run.tool_conf)
        attempts.append(TierAttempt(
            tier=tier, confidence=conf.weighted_sum(), grounded=grounded,
            cost_usd=gw.ledger.total_cost_usd - cost_before,
        ))
        result = (answers, text, citations, grounded, conf, tier)
        if conf.weighted_sum() >= bar:
            break
    assert result is not None  # the loop runs at least once
    return (*result, attempts)


def _answer_turn(
    question: str,
    subs: list[str],
    kb_intent: str | None,
    tool_sources: list[Hit],
    gw: ModelGateway,
    model: str | None,
    plan_id: str | None = None,
) -> list[RagAnswer]:
    """Generate the grounded answer(s) for a turn.

    With tool sources present, ground the WHOLE question over (tool sources + KB hits) in
    one pass — a deductible+MRI turn must cite both the member account and the benefit
    rule. With no tools, fall back to the per-sub-question RAG path (handles comparatives).

    `plan_id` scopes plan-specific SBC chunks to the member's own plan so a coverage
    answer is never grounded in another plan's Summary of Benefits and Coverage.
    """
    if tool_sources:
        kb_hits = (
            retrieval.retrieve(question, intent=kb_intent, gateway=gw, plan_id=plan_id)
            if kb_intent else []
        )
        sources = tool_sources + kb_hits
        ans = generate_grounded(
            question, sources, gateway=gw, model=model,
            retrieval_conf=retrieval_conf(sources),
        )
        return [ans]
    return _answer_subs(subs, kb_intent, gw, model=model)


def _provider_turn(question, intent, intent_conf, safety, gw) -> TurnResult:
    """provider_search: run the provider tool and format a structured, grounded reply."""
    # Pull a specialty hint from the question (best-effort; the tool also filters loosely).
    specialty = specialty_hint(question)
    out = provider_search(ProviderSearchInput(specialty=specialty, limit=5))
    conf = ConfidenceBreakdown(intent_conf=intent_conf, tool_conf=1.0 if out.complete else 0.0)
    if not out.providers:
        return _escalate(question, intent, [question], [], conf,
                         "no_providers_found", safety, "human", gw.ledger.total_cost_usd,
                         tools_run=["provider_search"])
    lines = [
        f"{p.name}" + (f" ({p.specialty})" if p.specialty else "")
        + (f" — {p.city}, {p.state}" if p.city else "")
        + ("" if p.accepting_new else " (not accepting new patients)")
        for p in out.providers
    ]
    answer = "In-network providers:\n" + "\n".join(f"- {ln}" for ln in lines)
    citations = [Citation(f"tool:provider:{p.npi}", p.name, "", None) for p in out.providers]
    return TurnResult(
        question=question, intent=intent, sub_questions=[question], answer=answer,
        citations=citations, grounded=True, escalated=False, handoff=None,
        confidence=conf, tier_used="none", safety_flag=safety,
        cost_usd=gw.ledger.total_cost_usd, rag_answers=[],
        tools_run=["provider_search"],
    )

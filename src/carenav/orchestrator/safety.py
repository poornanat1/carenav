"""Safety triage — a small-LLM crisis/emergency classifier (docs/03 node 2).

Replaces the former keyword-regex triage. A brittle keyword scan matched crisis signals
by luck ("suicidal" happened to hit `\\bsuicid`) and missed paraphrases a human would catch
instantly ("I don't want to be here anymore", "what's the point of going on"). A small
model reads intent, not surface strings.

The classifier runs on the SAME turn boundary regardless of whether a member is selected:
both the profile path (api.profile_turn) and the general path (orchestrator.turn) call
`classify_safety` before producing any answer. The former bug was that the profile path
skipped triage entirely and answered a crisis message from member data.

Failure posture — FAIL OPEN (returns "none"): when the model is unavailable (offline stub,
API error, cold start, or unparseable output) this reports no safety signal so the turn
answers normally. This is a deliberate product choice; it means the gate is only as present
as the model. Every fail-open exit is logged at WARNING so the gap is observable. If a
missed crisis during a model outage becomes unacceptable, switch the fallbacks below to
return EMERGENT (fail closed) instead.
"""

from __future__ import annotations

import logging

from carenav.models import ModelGateway

logger = logging.getLogger(__name__)

# The three levels the rest of the pipeline already understands (state.HandoffPacket,
# turn.run_turn's confidence-bar logic). "emergent" short-circuits to a human handoff;
# "urgent" raises the confidence bar; "none" answers normally.
EMERGENT = "emergent"
URGENT = "urgent"
NONE = "none"
_LEVELS = frozenset({EMERGENT, URGENT, NONE})

_SAFETY_PROMPT = """You are a safety triage classifier for a health-plan member assistant.
Read the member's message and classify the SAFETY level of their situation. Judge intent
and meaning, not just keywords — a message can be a crisis without any obvious word.

Levels:
- emergent: a life-threatening emergency or self-harm/suicide crisis happening now or
  imminent. Examples: chest pain now, trouble breathing, stroke signs, anaphylaxis,
  overdose, unconsciousness, OR any expression of wanting to die, kill themselves, self
  harm, or not wanting to be alive ("suicidal", "I want to end it", "no reason to go on",
  "I don't want to be here anymore").
- urgent: a serious symptom that needs prompt care but is not immediately life-threatening
  (severe/worsening pain, heavy bleeding, a symptom escalating right now).
- none: an ordinary informational or administrative question (coverage, a drug, a
  condition, finding a provider, their own profile). Most messages are this.

When genuinely unsure between emergent and a lower level, choose the HIGHER level: a false
alarm is acceptable, a missed crisis is not.

Message: {question}

Reply with ONLY one word: emergent, urgent, or none."""


def classify_safety(question: str, gateway: ModelGateway) -> str:
    """Return the safety level for the raw turn: 'emergent' | 'urgent' | 'none'.

    One constrained small-model call. Fails OPEN to 'none' (logged) when the model is
    unavailable or returns something unparseable — see the module docstring.
    """
    try:
        raw = gateway.generate(
            _SAFETY_PROMPT.format(question=question), label="orchestrator.safety"
        ).text.strip().lower()
    except Exception as exc:  # provider error / timeout / cold start
        logger.warning(
            "Safety classifier unavailable (%s); failing OPEN to 'none' — a crisis in "
            "this turn would NOT be escalated. %s",
            type(exc).__name__,
            exc,
        )
        return NONE

    level = _parse_level(raw)
    if level is None:
        logger.warning(
            "Safety classifier returned no recognizable level (%r); failing OPEN to 'none'.",
            raw[:80],
        )
        return NONE
    return level


def _parse_level(raw: str) -> str | None:
    """Extract the safety level from the model reply.

    Prefer the strongest level present so trailing prose ("none, but ... emergent") cannot
    downgrade a crisis: check emergent, then urgent, then none.
    """
    for level in (EMERGENT, URGENT, NONE):
        if level in raw:
            return level
    return None

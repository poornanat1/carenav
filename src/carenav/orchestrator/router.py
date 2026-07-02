"""route node — safety triage + intent classification (docs/03 nodes 2+4).

Layers, cheapest first:
  1. Safety triage — a small-LLM crisis/emergency classifier (orchestrator.safety). It
     replaced the former keyword-regex scan, which matched by surface string and missed
     paraphrases. The missed-escalation hard gate (docs/09) says a false positive here is
     acceptable; a miss is not. Runs before anything else.
  2. Tier-0 keyword fast path — unambiguous intents skip the LLM entirely.
  3. Tier-1 LLM classify — one small-model call constrained to the router vocabulary.

Returns (intent, intent_conf, safety_flag).
"""

from __future__ import annotations

import re

from carenav.agents.providers import SPECIALTY_TERMS
from carenav.models import ModelGateway
from carenav.orchestrator.safety import EMERGENT, classify_safety
from carenav.orchestrator.state import ALL_INTENTS, SAFETY_INTENT

# Alternation of provider/specialty nouns, shared with api.query_analyzer via SPECIALTY_TERMS.
_SPECIALTY_ALT = "|".join(re.escape(t) for t in SPECIALTY_TERMS)

# --- 2. tier-0 keyword fast path -----------------------------------------------------------

_FAST_PATHS: list[tuple[str, str]] = [
    (r"\bside effects?\b|\bdosage\b|\bhow (do|should) i take\b|\bdrug\b|\bmedication\b",
     "medication"),
    (rf"\bfind (a |an )?({_SPECIALTY_ALT})\b", "provider_search"),
    (rf"\b(recommend|recommendation|suggest|suggestion)s?\b.*\b({_SPECIALTY_ALT})\b",
     "provider_search"),
    (rf"\b(in[- ]network|near me)\b.*\b({_SPECIALTY_ALT})\b", "provider_search"),
    (r"\bdeductible\b|\bcopay\b|\bcoinsurance\b|\bprior auth", "coverage"),
    (r"\bcovered?\b.*\bplan\b|\bplan\b.*\bcover", "coverage"),
]


def _fast_path(question: str) -> str | None:
    low = question.lower()
    for pat, intent in _FAST_PATHS:
        if re.search(pat, low):
            return intent
    return None


# --- 3. tier-1 LLM classify ----------------------------------------------------------------

_CLASSIFY_PROMPT = """Classify this health-plan member question into exactly ONE intent label.

Labels:
- medication: about a drug — what it does, how to take it, side effects, interactions.
- condition_info: about a NAMED disease/condition — what it is, its symptoms, how it is treated.
- self_care: what the member should do themselves for a symptom or situation.
- coverage: what their insurance plan covers, costs, deductibles, prior authorization.
- benefit: plan benefit rules or claims (copays for a service, why a claim was denied).
- provider_search: finding a doctor, specialist, or facility.
- emergency: a medical emergency happening right now.
- out_of_scope: asking YOU to diagnose them (e.g. "what illness do I have?", "diagnose
  this"), treatment or dosing decisions, small talk, non-health, requests about other
  people's data. Diagnosis requests are ALWAYS out_of_scope, never condition_info.

Question: {question}

Reply with ONLY the label, nothing else."""


def route(question: str, gateway: ModelGateway) -> tuple[str | None, float, str]:
    """Classify the turn. Returns (intent, intent_conf, safety_flag)."""
    safety = classify_safety(question, gateway)
    if safety == EMERGENT:
        return SAFETY_INTENT, 1.0, safety

    fast = _fast_path(question)
    if fast:
        return fast, 0.9, safety

    raw = gateway.generate(
        _CLASSIFY_PROMPT.format(question=question), label="orchestrator.route"
    ).text.strip().lower()
    # Take the first known label appearing in the reply (models sometimes add prose).
    for label in ALL_INTENTS:
        if label in raw:
            return label, 0.75, safety
    return None, 0.3, safety  # unknown → KB-wide search, low confidence

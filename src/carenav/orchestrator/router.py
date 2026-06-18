"""route node — safety triage + intent classification (docs/03 nodes 2+4).

Three layers, cheapest first:
  1. EMERGENT triage — deterministic keyword scan for can't-miss signals (chest pain,
     stroke signs, suicide, anaphylaxis). The missed-escalation hard gate (docs/09) says
     a false positive here is acceptable; a miss is not. Runs before anything else.
  2. Tier-0 keyword fast path — unambiguous intents skip the LLM entirely.
  3. Tier-1 LLM classify — one small-model call constrained to the router vocabulary.

Returns (intent, intent_conf, safety_flag).
"""

from __future__ import annotations

import re

from carenav.models import ModelGateway
from carenav.orchestrator.state import ALL_INTENTS, SAFETY_INTENT

# --- 1. emergent triage ------------------------------------------------------------------

_EMERGENT_PATTERNS = [
    r"\bchest pain\b.*\b(now|right now|currently)\b",
    r"\b(now|right now|currently)\b.*\bchest pain\b",
    r"\bcan'?t breathe\b|\bcannot breathe\b|\btrouble breathing right now\b",
    r"\bsuicid|\bkill myself\b|\bend my life\b|\bself[- ]harm\b",
    r"\boverdosed?\b.*\b(just|now|today)\b",
    r"\bstroke\b.*\b(having|right now)\b|\bface (is )?droop",
    r"\bsevere allergic reaction\b|\banaphyla",
    r"\bunconscious\b|\bpassed out\b|\bnot breathing\b",
    r"\b911\b|\bemergency\b.*\bnow\b",
]


def triage(question: str) -> str:
    """Return the safety flag for the raw turn: 'emergent' | 'urgent' | 'none'."""
    low = question.lower()
    for pat in _EMERGENT_PATTERNS:
        if re.search(pat, low):
            return "emergent"
    # Urgent (raises the confidence bar, docs/06) — symptom-now phrasing short of emergent.
    if re.search(r"\b(severe|worst|intense)\b.*\b(pain|bleeding|headache)\b", low):
        return "urgent"
    return "none"


# --- 2. tier-0 keyword fast path -----------------------------------------------------------

_FAST_PATHS: list[tuple[str, str]] = [
    (r"\bside effects?\b|\bdosage\b|\bhow (do|should) i take\b|\bdrug\b|\bmedication\b",
     "medication"),
    (r"\bfind (a |an )?(doctor|cardiologist|specialist|provider|dermatologist|"
     r"pediatrician|endocrinologist|orthopedist|neurologist|oncologist|ophthalmologist)\b",
     "provider_search"),
    (r"\b(recommend|recommendation|suggest|suggestion)s?\b.*\b(doctor|provider|"
     r"specialist|cardiologist|dermatologist|pediatrician|endocrinologist|orthopedist|"
     r"neurologist|oncologist|ophthalmologist)\b", "provider_search"),
    (r"\b(in[- ]network|near me)\b.*\b(doctor|provider|specialist|cardiologist|"
     r"dermatologist|pediatrician|endocrinologist|orthopedist|neurologist|oncologist|"
     r"ophthalmologist)\b", "provider_search"),
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
- condition_info: about a disease/condition — what it is, symptoms, diagnosis, treatment.
- self_care: what the member should do themselves for a symptom or situation.
- coverage: what their insurance plan covers, costs, deductibles, prior authorization.
- benefit: plan benefit rules or claims (copays for a service, why a claim was denied).
- provider_search: finding a doctor, specialist, or facility.
- emergency: a medical emergency happening right now.
- out_of_scope: none of the above (small talk, non-health, requests about other people's data).

Question: {question}

Reply with ONLY the label, nothing else."""


def route(question: str, gateway: ModelGateway) -> tuple[str | None, float, str]:
    """Classify the turn. Returns (intent, intent_conf, safety_flag)."""
    safety = triage(question)
    if safety == "emergent":
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

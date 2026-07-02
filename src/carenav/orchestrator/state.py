"""Turn state + result types for the orchestrator (docs/03, docs/06).

Carries a turn through route → decompose → plan → tool_exec → reflect → generate →
verify → respond | escalate. The remaining `redact` node and session persistence extend
this state rather than replace it; field names follow docs/03-orchestrator.md so adopting
a graph framework later stays mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from carenav.rag.agent import RagAnswer

# Router vocabulary. KB_INTENTS map to retrieval source_type filters
# (carenav/rag/retrieval.py INTENT_SOURCE_TYPES); the rest route elsewhere.
KB_INTENTS = ("medication", "condition_info", "self_care", "coverage", "benefit")
NON_KB_INTENTS = ("provider_search", "out_of_scope")
SAFETY_INTENT = "emergency"
ALL_INTENTS = (*KB_INTENTS, *NON_KB_INTENTS, SAFETY_INTENT)


@dataclass
class ConfidenceBreakdown:
    """docs/06: components in [0,1], combined by weighted_sum()."""

    intent_conf: float = 0.0
    retrieval_conf: float = 0.0
    tool_conf: float = 1.0      # KB-only turns have no required tool fields yet
    self_eval: float = 0.0      # grounded answers count as positive self-evaluation

    def weighted_sum(self) -> float:
        # Retrieval + groundedness dominate for KB turns; router confidence tempers.
        return max(
            0.0,
            min(
                1.0,
                0.20 * self.intent_conf
                + 0.40 * self.retrieval_conf
                + 0.10 * self.tool_conf
                + 0.30 * self.self_eval,
            ),
        )


@dataclass
class HandoffPacket:
    """Structured escalate_human output (docs/03) — never prose."""

    redacted_summary: str
    suspected_intent: str | None
    gathered: list[str]                 # citations / evidence collected so far
    reason: str                         # emergent_safety | low_conf_high_stakes |
    #                                     groundedness_fail | verify_fail | out_of_scope |
    #                                     provider_search_unsupported
    safety_flag: str                    # none | urgent | emergent


@dataclass
class TierAttempt:
    """One scored tier attempt inside _answer_at_tiers (eval telemetry, docs/09).

    Records the composite confidence each tier achieved so the eval harness can replay
    the tau_low/tau_high selection rule offline (the threshold sweep, docs/06) without
    re-running the suite per threshold.
    """

    tier: str                           # "small" | "frontier"
    confidence: float                   # ConfidenceBreakdown.weighted_sum() for the attempt
    grounded: bool
    cost_usd: float                     # ledger delta attributable to this attempt


@dataclass
class TurnResult:
    question: str
    intent: str | None
    sub_questions: list[str]
    answer: str                         # final user-facing text ("" when escalated)
    citations: list                     # carenav.rag.agent.Citation
    grounded: bool
    escalated: bool
    handoff: HandoffPacket | None
    confidence: ConfidenceBreakdown
    tier_used: str                      # "none" | "small" | "frontier" | "human"
    safety_flag: str                    # none | urgent | emergent
    cost_usd: float
    rag_answers: list[RagAnswer] = field(default_factory=list)
    tools_run: list[str] = field(default_factory=list)          # executed specialist tools
    tier_attempts: list[TierAttempt] = field(default_factory=list)
    # Distinct PII values tokenized this turn, by entity type (counts only, never values).
    # Populated by run_turn from the turn's PiiMap; feeds the telemetry PII audit metric.
    pii_entity_counts: dict[str, int] = field(default_factory=dict)

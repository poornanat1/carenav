"""Golden-fixture schema for the CUJ eval suite (docs/09-eval.md §6.1).

Fixtures are frozen dataclasses rather than YAML/JSON so they get ruff/mypy checking for
free — a typo'd intent or escalation reason fails `make lint`, not a 20-minute eval run.
They stay declarative: data only, no logic.

Placeholders ``{member_name}`` / ``{member_dob}`` / ``{member_id}`` / ``{member_address}``
/ ``{denied_service_code}`` in ``turns`` / ``planted_pii`` / ``answer_must_not_contain``
are filled at runtime from the member the MemberSpec resolves to (eval/members.py), so
the field-based redaction layer is exercised against the member's real record values.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MemberSpec:
    """Declarative member selection — resolved deterministically against the live DB.

    Traits (all must hold):
      * ``active``             — eligibility_status == "active"
      * ``partial_deductible`` — 0 < accumulator.deductible_met < plan.deductible
      * ``owed_claim``         — has a claim with member_responsibility > 0
      * ``denied_claim``       — has a claim with status == "denied"
      * ``has_claims``         — has at least one claim
      * ``has_conditions``     — has at least one diagnosed condition
    """

    traits: tuple[str, ...] = ("active",)


@dataclass(frozen=True)
class Expect:
    """Hard assertions on the FINAL TurnResult of a case (docs/09 §6.2: task success
    requires the LLM-judge rubric AND these — both must pass)."""

    # None = either outcome is policy-compliant (e.g. CUJ-10: decline OR answer within
    # the authenticated member's own context) — the rubric carries the real check.
    escalated: bool | None
    # Acceptable values; None = don't assert on that field.
    reasons: frozenset[str] | None = None            # handoff.reason
    intents: frozenset[str] | None = None            # TurnResult.intent
    safety_flags: frozenset[str] | None = None       # TurnResult.safety_flag
    tools: frozenset[str] = frozenset()              # must be ⊆ TurnResult.tools_run
    # Each prefix must match ≥1 citation chunk_id (e.g. "tool:member_account", "openfda-").
    citation_prefixes: frozenset[str] = frozenset()
    # Literal strings (post-placeholder-fill) that must NOT appear in the final answer.
    answer_must_not_contain: tuple[str, ...] = ()


@dataclass(frozen=True)
class CUJCase:
    id: str                                # "CUJ-6b" — unique across the suite
    cuj: str                               # "CUJ-6" — the journey this case belongs to
    description: str
    turns: tuple[str, ...]                 # ≥1; earlier turns are conversation setup
    member: MemberSpec | None              # None = run without a member_ref
    expect: Expect
    rubric: str                            # LLM-judge rubric; may reference {facts}
    # Raw PII strings that must NEVER appear in any captured model prompt (the PII-leak
    # hard gate sweeps every prompt of every case; these add case-specific probes).
    planted_pii: tuple[str, ...] = ()
    # Counts toward the missed-escalation HARD gate (docs/09: CUJ-6 and any
    # emergent/high-stakes case). safety_critical cases MUST expect escalation.
    safety_critical: bool = False
    # Included in the tau threshold-sweep phase (cases that short-circuit before tier
    # scoring — emergent triage, out-of-scope — carry no tier signal to sweep).
    sweepable: bool = True
    # Facts the judge rubric needs, resolved per-member by eval/members.py (numbers only —
    # never identifiers). Keys name resolver-provided facts, e.g. "deductible_remaining".
    rubric_facts: tuple[str, ...] = field(default=())

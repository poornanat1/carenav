"""The golden CUJ set (docs/09-eval.md §6.1) — one module per journey, aggregated here.

`validate_cases()` is the fixture linter: it runs in the hermetic test suite so a
malformed fixture (unknown intent, missing PII probes on CUJ-9, a CUJ-6 case that
doesn't expect escalation) fails `make test`, never a 20-minute eval run.
"""

from __future__ import annotations

from carenav.orchestrator.state import ALL_INTENTS
from eval.cujs import (
    cuj01_coverage,
    cuj02_deductible,
    cuj03_claim,
    cuj04_provider,
    cuj05_medication,
    cuj06_emergent,
    cuj07_diagnosis,
    cuj08_multiturn,
    cuj09_pii,
    cuj10_injection,
)
from eval.cujs.schema import CUJCase, Expect, MemberSpec

__all__ = ["ALL_CASES", "CUJCase", "Expect", "MemberSpec", "validate_cases"]

ALL_CASES: list[CUJCase] = [
    *cuj01_coverage.CASES,
    *cuj02_deductible.CASES,
    *cuj03_claim.CASES,
    *cuj04_provider.CASES,
    *cuj05_medication.CASES,
    *cuj06_emergent.CASES,
    *cuj07_diagnosis.CASES,
    *cuj08_multiturn.CASES,
    *cuj09_pii.CASES,
    *cuj10_injection.CASES,
]

# Vocabularies the fixtures must stay within (mirrors orchestrator/turn.py + agents).
ESCALATION_REASONS = frozenset({
    "emergent_safety", "out_of_scope", "member_context_required",
    "low_conf_high_stakes", "groundedness_fail", "verify_fail", "no_providers_found",
})
TOOL_NAMES = frozenset({"member_account", "benefit_lookup", "claims_lookup", "provider_search"})
MEMBER_TRAITS = frozenset({
    "active", "partial_deductible", "owed_claim", "denied_claim", "has_claims",
    "has_conditions",
})
SAFETY_FLAGS = frozenset({"none", "urgent", "emergent"})
ALL_CUJS = frozenset(f"CUJ-{n}" for n in range(1, 11))


def validate_cases(cases: list[CUJCase] | None = None) -> None:
    """Raise ValueError describing every fixture problem found (empty = valid)."""
    cases = ALL_CASES if cases is None else cases
    problems: list[str] = []
    seen_ids: set[str] = set()
    covered_cujs: set[str] = set()

    for c in cases:
        where = f"[{c.id}]"
        if c.id in seen_ids:
            problems.append(f"{where} duplicate case id")
        seen_ids.add(c.id)
        covered_cujs.add(c.cuj)
        if c.cuj not in ALL_CUJS:
            problems.append(f"{where} unknown cuj {c.cuj!r}")
        if not c.id.startswith(c.cuj):
            problems.append(f"{where} id does not start with its cuj {c.cuj!r}")
        if not c.turns:
            problems.append(f"{where} has no turns")
        if not c.rubric.strip():
            problems.append(f"{where} has an empty rubric")
        if c.expect.intents is not None and not c.expect.intents <= set(ALL_INTENTS):
            unknown = sorted(c.expect.intents - set(ALL_INTENTS))
            problems.append(f"{where} unknown intents {unknown}")
        if c.expect.reasons is not None and not c.expect.reasons <= ESCALATION_REASONS:
            unknown = sorted(c.expect.reasons - ESCALATION_REASONS)
            problems.append(f"{where} unknown reasons {unknown}")
        if not c.expect.tools <= TOOL_NAMES:
            problems.append(f"{where} unknown tools {sorted(c.expect.tools - TOOL_NAMES)}")
        if c.expect.safety_flags is not None and not c.expect.safety_flags <= SAFETY_FLAGS:
            problems.append(
                f"{where} unknown safety flags {sorted(c.expect.safety_flags - SAFETY_FLAGS)}"
            )
        if c.member is not None and not set(c.member.traits) <= MEMBER_TRAITS:
            unknown = sorted(set(c.member.traits) - MEMBER_TRAITS)
            problems.append(f"{where} unknown traits {unknown}")
        if c.safety_critical and c.expect.escalated is not True:
            problems.append(f"{where} safety_critical but does not expect escalation")
        if c.expect.reasons is not None and c.expect.escalated is not True:
            problems.append(f"{where} asserts escalation reasons without expecting escalation")
        # CUJ-specific invariants (docs/09).
        if c.cuj == "CUJ-6" and not c.safety_critical:
            problems.append(f"{where} CUJ-6 cases must be safety_critical (the hard gate)")
        if c.cuj == "CUJ-6" and c.sweepable:
            problems.append(f"{where} CUJ-6 short-circuits tier scoring — cannot be sweepable")
        if c.cuj == "CUJ-9" and not c.planted_pii:
            problems.append(f"{where} CUJ-9 cases must plant PII probes")
        # Placeholders that need a member require a MemberSpec to resolve them.
        blob = " ".join((*c.turns, *c.planted_pii, *c.expect.answer_must_not_contain))
        if "{member_" in blob and c.member is None:
            problems.append(f"{where} uses {{member_*}} placeholders without a MemberSpec")
        if "{denied_service_code}" in blob and (
            c.member is None or "denied_claim" not in c.member.traits
        ):
            problems.append(f"{where} uses {{denied_service_code}} without the denied_claim trait")

    missing = ALL_CUJS - covered_cujs
    if cases is ALL_CASES and missing:
        problems.append(f"golden set is missing {sorted(missing)}")

    if problems:
        raise ValueError("fixture validation failed:\n  " + "\n  ".join(problems))

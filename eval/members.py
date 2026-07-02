"""Deterministic member resolution for the golden CUJ fixtures.

A MemberSpec's traits become SQL filters; the first matching member (ORDER BY member_id)
is used, so the same DB snapshot always evals the same members. Placeholders in fixture
text are filled from the resolved record so the field-based redaction layer (docs/05) is
exercised against real values, and rubric {facts} carry NUMBERS ONLY — never identifiers —
so judge prompts stay out of PHI's way.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import exists, select

from carenav.agents import create_demo_member_ref
from carenav.data.db import session_scope
from carenav.data.models import Accumulator, Claim, Condition, Member, Plan
from eval.cujs.schema import CUJCase, MemberSpec


@dataclass(frozen=True)
class ResolvedMember:
    member_id: str
    member_ref: str
    plan_id: str
    # PHI values (used ONLY to fill fixture placeholders and to probe captured prompts
    # for leaks — never written to reports).
    name: str
    dob_iso: str
    address: str
    # Judge-facing facts: numbers/labels only, keyed by fixture rubric_facts names.
    facts: dict[str, str]


@dataclass(frozen=True)
class FilledCase:
    """A CUJCase with placeholders resolved against a live member (or no member)."""

    case: CUJCase
    member: ResolvedMember | None
    turns: tuple[str, ...]
    planted_pii: tuple[str, ...]
    answer_must_not_contain: tuple[str, ...]
    facts: dict[str, str]


class MemberResolutionError(RuntimeError):
    """No member in the dataset satisfies a fixture's MemberSpec."""


def _trait_stmt(traits: tuple[str, ...]):
    stmt = select(Member).order_by(Member.member_id)
    for trait in traits:
        if trait == "active":
            stmt = stmt.where(Member.eligibility_status == "active")
        elif trait == "partial_deductible":
            stmt = stmt.where(
                exists(
                    select(Accumulator.id)
                    .join(Plan, Plan.plan_id == Member.plan_id)
                    .where(
                        Accumulator.member_id == Member.member_id,
                        Accumulator.deductible_met > 0,
                        Accumulator.deductible_met < Plan.deductible,
                    )
                )
            )
        elif trait == "owed_claim":
            stmt = stmt.where(
                exists(
                    select(Claim.claim_id).where(
                        Claim.member_id == Member.member_id,
                        Claim.member_responsibility > 0,
                        Claim.status != "denied",
                    )
                )
            )
        elif trait == "denied_claim":
            stmt = stmt.where(
                exists(
                    select(Claim.claim_id).where(
                        Claim.member_id == Member.member_id, Claim.status == "denied"
                    )
                )
            )
        elif trait == "has_claims":
            stmt = stmt.where(
                exists(select(Claim.claim_id).where(Claim.member_id == Member.member_id))
            )
        elif trait == "has_conditions":
            stmt = stmt.where(
                exists(select(Condition.id).where(Condition.member_id == Member.member_id))
            )
        else:  # pragma: no cover — validate_cases() rejects unknown traits first
            raise ValueError(f"unknown member trait {trait!r}")
    return stmt


def _member_facts(session, member: Member) -> dict[str, str]:
    """Numbers-only ground truth for judge rubrics ({facts}) and fixture placeholders."""
    facts: dict[str, str] = {}
    plan = session.get(Plan, member.plan_id)
    acc = session.execute(
        select(Accumulator)
        .where(Accumulator.member_id == member.member_id)
        .order_by(Accumulator.plan_year.desc())
    ).scalars().first()
    if plan is not None:
        facts["deductible"] = f"${float(plan.deductible):.0f}"
        facts["oop_max"] = f"${float(plan.oop_max):.0f}"
        if acc is not None:
            met = float(acc.deductible_met)
            facts["deductible_met"] = f"${met:.0f}"
            facts["deductible_remaining"] = f"${max(float(plan.deductible) - met, 0):.0f}"
            facts["oop_met"] = f"${float(acc.oop_met):.0f}"
    denied = session.execute(
        select(Claim)
        .where(Claim.member_id == member.member_id, Claim.status == "denied")
        .order_by(Claim.claim_id)
    ).scalars().first()
    if denied is not None:
        facts["denied_service_code"] = denied.service_code
        facts["denial_reason"] = denied.denial_reason or ""
        facts["denied_billed"] = f"${float(denied.billed):.0f}"
    return facts


def resolve(spec: MemberSpec) -> ResolvedMember:
    """Deterministically pick the first member satisfying every trait."""
    with session_scope() as session:
        member = session.execute(_trait_stmt(spec.traits).limit(1)).scalars().first()
        if member is None:
            raise MemberResolutionError(
                f"no member satisfies traits {spec.traits!r} — check the dataset "
                "(make data) or relax the fixture's MemberSpec"
            )
        return ResolvedMember(
            member_id=member.member_id,
            member_ref=create_demo_member_ref(member.member_id),
            plan_id=member.plan_id,
            name=member.name,
            dob_iso=member.dob.isoformat(),
            address=member.address,
            facts=_member_facts(session, member),
        )


def _fill(text: str, m: ResolvedMember) -> str:
    filled = (
        text.replace("{member_name}", m.name)
        .replace("{member_dob}", m.dob_iso)
        .replace("{member_address}", m.address)
        .replace("{member_id}", m.member_id)
    )
    for key, value in m.facts.items():
        filled = filled.replace("{" + key + "}", value)
    return filled


def fill_case(case: CUJCase) -> FilledCase:
    """Resolve the case's member and fill every placeholder. Raises with the case id on
    an unsatisfiable MemberSpec so a bad fixture is named, not buried in a stack trace."""
    if case.member is None:
        return FilledCase(
            case=case, member=None, turns=case.turns, planted_pii=case.planted_pii,
            answer_must_not_contain=case.expect.answer_must_not_contain, facts={},
        )
    try:
        m = resolve(case.member)
    except MemberResolutionError as e:
        raise MemberResolutionError(f"[{case.id}] {e}") from e
    facts = {k: m.facts[k] for k in case.rubric_facts if k in m.facts}
    missing = [k for k in case.rubric_facts if k not in m.facts]
    if missing:
        raise MemberResolutionError(f"[{case.id}] resolver has no facts for {missing}")
    return FilledCase(
        case=case,
        member=replace(m, facts=facts) if case.rubric_facts else m,
        turns=tuple(_fill(t, m) for t in case.turns),
        planted_pii=tuple(_fill(p, m) for p in case.planted_pii),
        answer_must_not_contain=tuple(
            _fill(a, m) for a in case.expect.answer_must_not_contain
        ),
        facts=facts,
    )

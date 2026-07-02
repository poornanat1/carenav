"""Member/Account agent — plan, eligibility, accumulators (docs/04). No model calls."""

from __future__ import annotations

from sqlalchemy import select

from carenav.agents.contracts import MemberAccountInput, MemberAccountOutput
from carenav.agents.session import resolve_member_ref
from carenav.data.db import session_scope
from carenav.data.models import Accumulator, Member, Plan
from carenav.redaction import entities as E


def member_phi_values(member_ref: str | None) -> dict[str, str]:
    """The resolved member's PHI field values, for the deterministic redaction layer.

    docs/05: values CareNav itself injects (name/dob/address/member_id) can be redacted
    with certainty before any NER/regex guesswork. Empty when the ref doesn't resolve —
    the model + regex layers still carry the gate.
    """
    member_id = resolve_member_ref(member_ref)
    if member_id is None:
        return {}
    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            return {}
        return {
            E.NAME: member.name,
            E.DOB: member.dob.isoformat(),
            E.ADDRESS: member.address,
            E.MEMBER_ID: member.member_id,
        }


def member_account(inp: MemberAccountInput) -> MemberAccountOutput:
    out = MemberAccountOutput()
    member_id = resolve_member_ref(inp.member_ref)
    if member_id is None:
        out.mark_missing("member_ref")
        return out

    with session_scope() as session:
        member = session.get(Member, member_id)
        if member is None:
            out.mark_missing("member")
            return out
        plan = session.get(Plan, member.plan_id)
        acc = session.execute(
            select(Accumulator)
            .where(Accumulator.member_id == member_id)
            .order_by(Accumulator.plan_year.desc())
        ).scalars().first()

        out.plan_id = member.plan_id
        out.eligibility_status = member.eligibility_status
        out.coverage_start = member.coverage_start
        out.coverage_end = member.coverage_end
        if plan is not None:
            out.plan_name = plan.name
            out.deductible = float(plan.deductible)
            out.oop_max = float(plan.oop_max)
        else:
            out.mark_missing("plan")
        if acc is not None:
            out.deductible_met = float(acc.deductible_met)
            out.oop_met = float(acc.oop_met)
            out.plan_year = acc.plan_year
        else:
            out.mark_missing("accumulator")
    return out

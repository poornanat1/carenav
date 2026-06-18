"""Claims agent — claim status / amounts / denial reasons for a member (docs/04)."""

from __future__ import annotations

from sqlalchemy import select

from carenav.agents.contracts import ClaimRecord, ClaimsInput, ClaimsOutput
from carenav.agents.session import resolve_member_ref
from carenav.data.db import session_scope
from carenav.data.models import Claim


def claims_lookup(inp: ClaimsInput) -> ClaimsOutput:
    out = ClaimsOutput()
    member_id = resolve_member_ref(inp.member_ref)
    if member_id is None:
        out.mark_missing("member_ref")
        return out

    with session_scope() as session:
        stmt = select(Claim).where(Claim.member_id == member_id)
        if inp.claim_id:
            stmt = stmt.where(Claim.claim_id == inp.claim_id)
        if inp.service_code:
            stmt = stmt.where(Claim.service_code == inp.service_code)
        rows = session.execute(stmt.limit(inp.limit)).scalars().all()
        if (inp.claim_id or inp.service_code) and not rows:
            out.mark_missing("claim")
            return out
        out.claims = [
            ClaimRecord(
                claim_id=c.claim_id,
                service_code=c.service_code,
                status=c.status,
                billed=float(c.billed),
                allowed=float(c.allowed),
                paid=float(c.paid),
                member_responsibility=float(c.member_responsibility),
                denial_reason=c.denial_reason,
            )
            for c in rows
        ]
    return out

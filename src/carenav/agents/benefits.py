"""Coverage/Benefit agent — benefit-rule lookup for a plan + service (docs/04).

Resolves a free-text service mention ("an MRI", "seeing a specialist") to a benefit-rule
key via an alias map, then returns the structured rule. No model calls.
"""

from __future__ import annotations

import re

from sqlalchemy import select

from carenav.agents.contracts import BenefitLookupInput, BenefitLookupOutput
from carenav.data.db import session_scope
from carenav.data.models import BenefitRule

# Free-text → benefit-rule key. Keys must match the seed (data/seeds/benefit_rules.json).
_ALIASES: list[tuple[str, str]] = [
    (r"\bmri\b|\bct scan\b|\badvanced imaging\b|\bimaging\b", "MRI"),
    (r"\bspecialist\b", "specialist_visit"),
    (r"\bprimary care\b|\boffice visit\b|\bdoctor('s)? visit\b|\bpcp\b", "office_visit"),
    (
        r"\blab\b|\btest\b|\bblood (test|work|panel)\b|\bmetabolic panel\b",
        "lab_panel",
    ),
    (r"\bpreventive\b|\bannual (visit|checkup|physical)\b|\bwellness\b|\bscreening\b",
     "preventive_visit"),
    (r"\bemergency room\b|\b er \b|\ber visit\b|\bemergency\b", "emergency_room"),
]


def normalize_service(service: str) -> str | None:
    """Map a service mention to a benefit-rule key; pass through exact keys/codes."""
    s = f" {service.strip().lower()} "
    for pattern, key in _ALIASES:
        if re.search(pattern, s):
            return key
    return service.strip() or None


def benefit_lookup(inp: BenefitLookupInput) -> BenefitLookupOutput:
    out = BenefitLookupOutput(plan_id=inp.plan_id)
    key = normalize_service(inp.service)
    if key is None:
        out.mark_missing("service")
        return out
    out.service_key = key

    with session_scope() as session:
        rule = session.execute(
            select(BenefitRule).where(
                BenefitRule.plan_id == inp.plan_id, BenefitRule.key == key
            )
        ).scalars().first()
        if rule is None:
            out.mark_missing("benefit_rule")
            return out
        out.covered = rule.covered
        out.copay = float(rule.copay) if rule.copay is not None else None
        out.coinsurance = float(rule.coinsurance) if rule.coinsurance is not None else None
        out.prior_auth_required = rule.prior_auth_required
        out.notes = rule.notes
    return out

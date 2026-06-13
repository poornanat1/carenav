"""plan → tool_exec → reflect — the specialist-tool loop (docs/03 nodes 5-7, M2 slice).

The orchestrator decides which specialist agents a turn needs, runs them, and turns their
STRUCTURED outputs into groundable "sources" so the same citation + groundedness contract
that governs KB answers also governs benefit/claim/member facts. A turn like "did I meet my
deductible and is an MRI covered?" needs member_account (for the deductible) + benefit_lookup
(for MRI coverage) — two tools, one grounded answer.

Tool outputs become Hit-shaped pseudo-chunks with `tool:<name>:<field-group>` ids, so the
generator cites e.g. [CHUNK:tool:member_account] just as it cites a KB chunk, and the
groundedness check verifies the claim against the tool fact. Member PHI in these sources is
tokenized by the redaction layer (M3) at this boundary; here we only assemble.

`tool_conf` for the confidence breakdown is the fraction of run tools that returned complete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from carenav.agents import (
    BenefitLookupInput,
    ClaimsInput,
    MemberAccountInput,
    benefit_lookup,
    claims_lookup,
    member_account,
)
from carenav.agents.benefits import normalize_service
from carenav.agents.contracts import AgentOutput
from carenav.rag.retrieval import Hit

# Service mentions that trigger a benefit lookup (mirrors benefits._ALIASES coverage).
_SERVICE_RE = re.compile(
    r"\bmri\b|\bct scan\b|\bimaging\b|\bspecialist\b|\boffice visit\b|\bprimary care\b|"
    r"\blab\b|\bblood (test|work|panel)\b|\bpreventive\b|\bwellness\b|\bscreening\b|"
    r"\bemergency room\b|\ber visit\b",
    re.IGNORECASE,
)
_DEDUCTIBLE_RE = re.compile(
    r"\bdeductible\b|\bout[- ]of[- ]pocket\b|\boop\b|\bmet (my|the)\b", re.IGNORECASE
)
_CLAIM_RE = re.compile(
    r"\bclaim\b|\bdenied\b|\bdenial\b|\bbilled\b|\bwhy (was|did).*(pay|cover)", re.IGNORECASE
)
_ELIGIBILITY_RE = re.compile(
    r"\beligib|\bcoverage (start|end|date)|\bam i (still )?covered|\bmy plan\b", re.IGNORECASE
)


@dataclass
class ToolPlan:
    """Which tools a turn needs (the `plan` node's decision)."""

    needs_member: bool = False
    needs_benefit: bool = False
    needs_claims: bool = False
    service_mention: str | None = None


@dataclass
class ToolRun:
    """Results of the tool_exec + reflect pass."""

    sources: list[Hit] = field(default_factory=list)   # groundable pseudo-chunks
    outputs: dict[str, AgentOutput] = field(default_factory=dict)
    tool_conf: float = 1.0
    member_id_resolved: bool = True


def plan_tools(question: str, intent: str | None) -> ToolPlan:
    """`plan` node: decide which specialist tools this turn requires."""
    p = ToolPlan()
    svc = _SERVICE_RE.search(question)
    if svc:
        p.service_mention = svc.group(0)
    # Coverage/benefit turns, or any turn naming a service, want the benefit rule.
    if intent in ("coverage", "benefit") or p.service_mention:
        p.needs_benefit = True
    if _CLAIM_RE.search(question):
        p.needs_claims = True
    if _DEDUCTIBLE_RE.search(question) or _ELIGIBILITY_RE.search(question):
        p.needs_member = True
    # A benefit lookup needs the member's plan_id, so it implies a member lookup.
    if p.needs_benefit:
        p.needs_member = True
    return p


def _hit(tool_id: str, title: str, text: str) -> Hit:
    """Wrap a structured tool fact as a groundable pseudo-chunk."""
    return Hit(
        chunk_id=f"tool:{tool_id}",
        doc_id=f"tool:{tool_id}",
        source_type="tool",
        title=title,
        source_url="",
        last_reviewed=None,
        section_path=None,
        text=text,
        score=1.0,
    )


def _member_text(o) -> str:
    parts = []
    if o.plan_name:
        parts.append(f"The member is enrolled in the {o.plan_name} plan ({o.plan_id}).")
    if o.eligibility_status:
        parts.append(f"Their eligibility status is {o.eligibility_status}.")
    if o.deductible is not None and o.deductible_met is not None:
        parts.append(
            f"Their plan-year deductible is ${o.deductible:.0f} and they have met "
            f"${o.deductible_met:.0f} of it so far."
        )
    if o.oop_max is not None and o.oop_met is not None:
        parts.append(
            f"Their out-of-pocket maximum is ${o.oop_max:.0f} and they have met "
            f"${o.oop_met:.0f} of it."
        )
    return " ".join(parts)


def _benefit_text(o) -> str:
    if o.covered is None:
        return ""
    svc = (o.service_key or "the service").replace("_", " ")
    cov = "covered" if o.covered else "not covered"
    cost = (
        f"a ${o.copay:.0f} copay" if o.copay is not None
        else (f"{o.coinsurance:.0%} coinsurance after the deductible"
              if o.coinsurance is not None else "cost sharing per the plan")
    )
    auth = " Prior authorization is required." if o.prior_auth_required else ""
    note = f" {o.notes}" if o.notes else ""
    return f"Under this plan, {svc} is {cov} with {cost}.{auth}{note}"


def _claims_text(o) -> str:
    if not o.claims:
        return ""
    lines = []
    for c in o.claims[:5]:
        base = (f"Claim {c.claim_id} ({c.service_code}) is {c.status}: billed ${c.billed:.0f}, "
                f"member responsibility ${c.member_responsibility:.0f}")
        if c.denial_reason:
            base += f", denial reason: {c.denial_reason}"
        lines.append(base + ".")
    return " ".join(lines)


def exec_and_reflect(question: str, member_ref: str | None, plan: ToolPlan) -> ToolRun:
    """`tool_exec` + `reflect`: run the planned tools, assemble sources, compute tool_conf."""
    run = ToolRun()
    completes: list[bool] = []

    member_out = None
    if plan.needs_member:
        member_out = member_account(MemberAccountInput(member_ref=member_ref or ""))
        run.outputs["member_account"] = member_out
        completes.append(member_out.complete)
        if "member_ref" in member_out.missing:
            run.member_id_resolved = False
        text = _member_text(member_out)
        if text:
            run.sources.append(_hit("member_account", "Your member account", text))

    if plan.needs_benefit and member_out is not None and member_out.plan_id:
        service = plan.service_mention or question
        ben = benefit_lookup(BenefitLookupInput(plan_id=member_out.plan_id, service=service))
        run.outputs["benefit_lookup"] = ben
        completes.append(ben.complete)
        text = _benefit_text(ben)
        if text:
            run.sources.append(_hit("benefit_lookup", "Your plan benefits", text))

    if plan.needs_claims:
        cl = claims_lookup(ClaimsInput(member_ref=member_ref or ""))
        run.outputs["claims_lookup"] = cl
        completes.append(cl.complete)
        text = _claims_text(cl)
        if text:
            run.sources.append(_hit("claims_lookup", "Your claims", text))

    run.tool_conf = (sum(completes) / len(completes)) if completes else 1.0
    return run


def normalize_service_mention(service: str) -> str | None:
    return normalize_service(service)

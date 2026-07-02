"""plan → tool_exec → reflect — the specialist-tool loop (docs/03 nodes 5-7).

The orchestrator decides which specialist agents a turn needs, runs them, and turns their
STRUCTURED outputs into groundable "sources" so the same citation + groundedness contract
that governs KB answers also governs benefit/claim/member facts. A turn like "did I meet my
deductible and is an MRI covered?" needs member_account (for the deductible) + benefit_lookup
(for MRI coverage) — two tools, one grounded answer.

Tool outputs become Hit-shaped pseudo-chunks with `tool:<name>:<field-group>` ids, so the
generator cites e.g. [CHUNK:tool:member_account] just as it cites a KB chunk, and the
groundedness check verifies the claim against the tool fact. Member PHI in these sources is
tokenized by the redaction layer at this boundary; here we only assemble.

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
from carenav.agents.benefits import SERVICE_KEYS, normalize_service, service_mention_re
from carenav.agents.contracts import AgentOutput
from carenav.models import ModelGateway
from carenav.rag.retrieval import Hit

_SERVICE_KEYS = set(SERVICE_KEYS)

_SERVICE_CLASSIFY_PROMPT = """Classify the requested health-plan service into one benefit key.

Allowed keys:
- MRI: advanced imaging such as MRI, CT, or diagnostic imaging.
- specialist_visit: specialist clinician visits.
- office_visit: primary care or general office visits.
- lab_panel: diagnostic lab tests, blood work, tumor-marker tests, chemistry panels,
  or other ordered laboratory testing.
- preventive_visit: annual physicals, wellness visits, preventive screenings.
- emergency_room: emergency room or ER visits.
- null: not enough information to map to one key.

Question: {question}

Reply with only one allowed key."""

# Service mentions that trigger a benefit lookup. Derived from benefits._ALIASES so the
# routing vocabulary and the normalizer can't drift apart.
_SERVICE_RE = service_mention_re()
_DEDUCTIBLE_RE = re.compile(
    r"\bdeductible\b|\bout[- ]of[- ]pocket\b|\boop\b|\bmet (my|the)\b", re.IGNORECASE
)
_CLAIM_RE = re.compile(
    r"\bclaims?\b|\bdenied\b|\bdenial\b|\bbilled\b|\bwhy (was|did).*(pay|cover)", re.IGNORECASE
)
# A bare service/procedure code on a claim line, e.g. "service code 185347001". 6+ digits.
_SERVICE_CODE_RE = re.compile(r"\b\d{6,}\b")
# A service/procedure code names a specific claim line on the member's account
# ("more information on service code 185347001"). These reference the member's claims,
# not the plan's benefit rules, so they route to the claims tool.
_CLAIM_CODE_RE = re.compile(
    r"\bservice code\b|\bprocedure code\b|\bclaim (id|number|#)\b|\bcpt\b|\bhcpcs\b|" +
    _SERVICE_CODE_RE.pattern,
    re.IGNORECASE,
)


def _service_code_in(question: str) -> str | None:
    """The first bare service/procedure code in the question, if any."""
    m = _SERVICE_CODE_RE.search(question)
    return m.group(0) if m else None
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
    plan_id: str | None = None   # resolved member plan, to scope plan-specific KB (SBC)


def plan_tools(question: str, intent: str | None) -> ToolPlan:
    """`plan` node: decide which specialist tools this turn requires."""
    p = ToolPlan()
    # A specific service/procedure/claim code refers to one of the member's claim lines,
    # not the plan's benefit schedule. Route it to the claims tool and do NOT treat it as
    # a benefit-coverage question (which would look up a category that doesn't exist and
    # report "not found").
    claim_code = bool(_CLAIM_CODE_RE.search(question))
    svc = _SERVICE_RE.search(question)
    if svc:
        p.service_mention = svc.group(0)
    claim_mention = bool(_CLAIM_RE.search(question))
    # Coverage/benefit turns, or any turn naming a benefit service, want the benefit rule —
    # unless the turn is about a specific claim code, or is a claims question naming no
    # service (a benefit lookup of nothing returns incomplete and only drags tool_conf).
    if (intent in ("coverage", "benefit") or p.service_mention) and not claim_code:
        if p.service_mention or not claim_mention:
            p.needs_benefit = True
    if claim_mention or claim_code:
        p.needs_claims = True
    if _DEDUCTIBLE_RE.search(question) or _ELIGIBILITY_RE.search(question):
        p.needs_member = True
    # Both claims and benefit lookups need the member resolved.
    if p.needs_benefit or p.needs_claims:
        p.needs_member = True
    return p


def infer_service_category(question: str, gateway: ModelGateway) -> str | None:
    """Use the model to map unusual service names to a constrained benefit category."""
    try:
        raw = gateway.generate(
            _SERVICE_CLASSIFY_PROMPT.format(question=question),
            label="orchestrator.service_category",
        ).text.strip()
    except Exception:
        return None
    normalized = raw.strip().strip("\"'`.").split()[0].strip("\"'`.,")
    return normalized if normalized in _SERVICE_KEYS else None


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


def _benefit_text(o, requested_service: str | None = None) -> str:
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
    mapping = (
        f"The requested service was categorized for benefit lookup as {svc}. "
        if requested_service and normalize_service(requested_service) != o.service_key
        else ""
    )
    return f"{mapping}Under this plan, {svc} is {cov} with {cost}.{auth}{note}"


def _claim_line(c) -> str:
    base = (
        f"Claim {c.claim_id} for service code {c.service_code} is {c.status}: "
        f"billed ${c.billed:.0f}, plan paid ${c.paid:.0f}, "
        f"member responsibility ${c.member_responsibility:.0f}"
    )
    if c.denial_reason:
        base += f", denial reason: {c.denial_reason}"
    return base + "."


def _claims_text(o, question: str | None = None) -> str:
    if not o.claims:
        return ""
    # If the question names a specific code, surface that claim first so it is always in
    # the grounded sources even when the member has many claims.
    code = _service_code_in(question) if question else None
    matched = [c for c in o.claims if code and c.service_code == code]
    others = [c for c in o.claims if c not in matched]
    ordered = matched + others
    return " ".join(_claim_line(c) for c in ordered[:5])


def exec_and_reflect(
    question: str,
    member_ref: str | None,
    plan: ToolPlan,
    gateway: ModelGateway | None = None,
) -> ToolRun:
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
        run.plan_id = member_out.plan_id
        text = _member_text(member_out)
        if text:
            run.sources.append(_hit("member_account", "Your member account", text))

    if plan.needs_benefit and member_out is not None and member_out.plan_id:
        inferred_service = None
        if plan.service_mention is None and gateway is not None:
            inferred_service = infer_service_category(question, gateway)
        service = plan.service_mention or inferred_service or question
        ben = benefit_lookup(BenefitLookupInput(plan_id=member_out.plan_id, service=service))
        run.outputs["benefit_lookup"] = ben
        completes.append(ben.complete)
        text = _benefit_text(ben, requested_service=question if service != question else None)
        if text:
            run.sources.append(_hit("benefit_lookup", "Your plan benefits", text))

    if plan.needs_claims:
        # If the question names a specific service code, filter to that claim so it is
        # found even when the member has hundreds of claims (the default lookup caps at a
        # few recent ones). Fall back to recent claims when no code is named.
        code = _service_code_in(question)
        cl = claims_lookup(ClaimsInput(member_ref=member_ref or "", service_code=code))
        if code and not cl.claims:
            # Named code not on the member's claims — show recent claims so the answer can
            # say so against real data rather than escalating.
            cl = claims_lookup(ClaimsInput(member_ref=member_ref or ""))
        run.outputs["claims_lookup"] = cl
        completes.append(cl.complete)
        text = _claims_text(cl, question)
        if text:
            run.sources.append(_hit("claims_lookup", "Your claims", text))

    run.tool_conf = (sum(completes) / len(completes)) if completes else 1.0
    return run

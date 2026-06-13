"""Typed Pydantic input/output contracts for the specialist agents (docs/04).

Design rules enforced here by shape:
  * agents return STRUCTURED DATA, never prose — the orchestrator owns generation;
  * every output carries a completeness signal (`complete` + `missing`) feeding
    `tool_conf` in the confidence breakdown (docs/06);
  * member-facing agents take an opaque `member_ref`, never a member_id.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    """Base: the completeness signal every agent surfaces."""

    complete: bool = True
    missing: list[str] = Field(default_factory=list)

    def mark_missing(self, *fields: str) -> None:
        self.missing.extend(fields)
        self.complete = False


# --- Member/Account -------------------------------------------------------------------------

class MemberAccountInput(BaseModel):
    member_ref: str


class MemberAccountOutput(AgentOutput):
    plan_id: str | None = None
    plan_name: str | None = None
    eligibility_status: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    deductible: float | None = None
    deductible_met: float | None = None
    oop_max: float | None = None
    oop_met: float | None = None
    plan_year: int | None = None


# --- Coverage/Benefit -----------------------------------------------------------------------

class BenefitLookupInput(BaseModel):
    plan_id: str
    service: str  # a service_code, a benefit category key, or a common phrase (aliased)


class BenefitLookupOutput(AgentOutput):
    plan_id: str | None = None
    service_key: str | None = None      # the normalized benefit-rule key that matched
    covered: bool | None = None
    copay: float | None = None
    coinsurance: float | None = None
    prior_auth_required: bool | None = None
    notes: str | None = None


# --- Claims ----------------------------------------------------------------------------------

class ClaimRecord(BaseModel):
    claim_id: str
    service_code: str
    status: str
    billed: float
    allowed: float
    paid: float
    member_responsibility: float
    denial_reason: str | None = None


class ClaimsInput(BaseModel):
    member_ref: str
    claim_id: str | None = None         # specific claim, else recent claims
    limit: int = 5


class ClaimsOutput(AgentOutput):
    claims: list[ClaimRecord] = Field(default_factory=list)


# --- Provider search ---------------------------------------------------------------------------

class ProviderRecord(BaseModel):
    npi: str
    name: str
    specialty: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    accepting_new: bool = True
    in_network: bool = True


class ProviderSearchInput(BaseModel):
    specialty: str | None = None
    state: str | None = None
    plan_id: str | None = None          # filter to the plan's network when known
    accepting_new: bool | None = None
    limit: int = 5


class ProviderSearchOutput(AgentOutput):
    providers: list[ProviderRecord] = Field(default_factory=list)

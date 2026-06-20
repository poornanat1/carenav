"""agents — specialist tools (docs/04-agents.md).

Typed Pydantic in/out contracts; structured data, never prose; no model calls; every
output carries a completeness signal feeding tool_conf. member_ref → member_id
resolution happens here (session.py), never in graph state or prompts.
"""

from carenav.agents.benefits import benefit_lookup
from carenav.agents.claims import claims_lookup
from carenav.agents.contracts import (
    BenefitLookupInput,
    BenefitLookupOutput,
    ClaimsInput,
    ClaimsOutput,
    MemberAccountInput,
    MemberAccountOutput,
    ProviderSearchInput,
    ProviderSearchOutput,
)
from carenav.agents.member import member_account
from carenav.agents.providers import provider_search, specialty_hint
from carenav.agents.session import create_demo_member_ref, create_member_ref, resolve_member_ref

__all__ = [
    "member_account", "benefit_lookup", "claims_lookup", "provider_search", "specialty_hint",
    "create_member_ref", "create_demo_member_ref", "resolve_member_ref",
    "MemberAccountInput", "MemberAccountOutput",
    "BenefitLookupInput", "BenefitLookupOutput",
    "ClaimsInput", "ClaimsOutput",
    "ProviderSearchInput", "ProviderSearchOutput",
]

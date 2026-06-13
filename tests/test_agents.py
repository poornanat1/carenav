"""Specialist-agent tests against the live Postgres data (read-only).

Picks a real loaded member, issues a member_ref, and asserts the typed structured outputs
+ completeness signals. Requires Postgres with the data pipeline already run. No writes.
"""

import pytest
from sqlalchemy import select

from carenav.agents import (
    BenefitLookupInput,
    ClaimsInput,
    MemberAccountInput,
    ProviderSearchInput,
    benefit_lookup,
    claims_lookup,
    create_member_ref,
    member_account,
    provider_search,
)
from carenav.agents.session import clear_sessions
from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
def a_member():
    """A real member_id + an issued opaque ref. Cleared after."""
    from carenav.data.db import session_scope
    from carenav.data.models import Member

    with session_scope() as s:
        mid = s.scalar(select(Member.member_id).limit(1))
    assert mid, "no members loaded — run the data pipeline first"
    ref = create_member_ref(mid)
    yield mid, ref
    clear_sessions()


def test_member_account_resolves_ref_and_returns_plan(a_member):
    _mid, ref = a_member
    out = member_account(MemberAccountInput(member_ref=ref))
    assert out.plan_id and out.plan_id.startswith("PLN-")
    assert out.eligibility_status in ("active", "inactive")
    assert out.deductible is not None and out.deductible_met is not None


def test_member_account_unknown_ref_is_incomplete():
    out = member_account(MemberAccountInput(member_ref="mref_does_not_exist"))
    assert not out.complete and "member_ref" in out.missing
    assert out.plan_id is None  # never fabricates


def test_benefit_lookup_normalizes_service(a_member):
    _mid, ref = a_member
    plan = member_account(MemberAccountInput(member_ref=ref)).plan_id
    out = benefit_lookup(BenefitLookupInput(plan_id=plan, service="do I need an MRI"))
    assert out.service_key == "MRI"
    assert out.covered is not None
    assert out.prior_auth_required is True  # MRI requires prior auth in the seed


def test_benefit_lookup_unknown_service_is_incomplete(a_member):
    _mid, ref = a_member
    plan = member_account(MemberAccountInput(member_ref=ref)).plan_id
    out = benefit_lookup(BenefitLookupInput(plan_id=plan, service="zzz unknown service"))
    assert not out.complete  # no matching rule


def test_claims_lookup_returns_structured_records(a_member):
    _mid, ref = a_member
    out = claims_lookup(ClaimsInput(member_ref=ref, limit=3))
    # The member may have 0 claims; if any, they must be fully typed.
    for c in out.claims:
        assert c.claim_id and c.status
        assert c.billed >= 0 and c.member_responsibility >= 0


def test_provider_search_filters_by_specialty():
    out = provider_search(ProviderSearchInput(specialty="Cardiology", limit=5))
    assert out.providers, "no cardiology providers in the NPPES load"
    for p in out.providers:
        assert p.npi and p.name


def test_agents_never_call_a_model(a_member):
    # Agents are pure DB lookups: a fresh gateway sees zero calls after running them.
    from carenav.models import ModelGateway

    gw = ModelGateway()
    _mid, ref = a_member
    member_account(MemberAccountInput(member_ref=ref))
    provider_search(ProviderSearchInput(specialty="Cardiology"))
    assert gw.ledger.calls == []  # no generate/embed happened

"""Provider-search agent — in-network providers by specialty/state (docs/04)."""

from __future__ import annotations

from sqlalchemy import select

from carenav.agents.contracts import ProviderRecord, ProviderSearchInput, ProviderSearchOutput
from carenav.data.db import session_scope
from carenav.data.models import PlanNetwork, Provider


def provider_search(inp: ProviderSearchInput) -> ProviderSearchOutput:
    out = ProviderSearchOutput()
    with session_scope() as session:
        stmt = select(Provider)
        in_network_npis: set[str] | None = None
        if inp.plan_id:
            in_network_npis = set(
                session.execute(
                    select(PlanNetwork.npi).where(
                        PlanNetwork.plan_id == inp.plan_id, PlanNetwork.in_network.is_(True)
                    )
                ).scalars()
            )
            if in_network_npis:
                stmt = stmt.where(Provider.npi.in_(in_network_npis))
        if inp.specialty:
            stmt = stmt.where(Provider.specialty.ilike(f"%{inp.specialty}%"))
        if inp.state:
            stmt = stmt.where(Provider.state == inp.state.upper())
        if inp.accepting_new is not None:
            stmt = stmt.where(Provider.accepting_new.is_(inp.accepting_new))
        rows = session.execute(stmt.limit(inp.limit)).scalars().all()
        out.providers = [
            ProviderRecord(
                npi=p.npi,
                name=p.name,
                specialty=p.specialty,
                address=p.address,
                city=p.city,
                state=p.state,
                accepting_new=p.accepting_new,
                in_network=(in_network_npis is None or p.npi in in_network_npis),
            )
            for p in rows
        ]
        if not out.providers:
            out.mark_missing("providers")
    return out

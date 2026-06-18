"""Provider-search agent — in-network providers by specialty/state (docs/04)."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from carenav.agents.contracts import ProviderRecord, ProviderSearchInput, ProviderSearchOutput
from carenav.data.db import session_scope
from carenav.data.models import PlanNetwork, Provider


@contextmanager
def _session_for(session: Session | None):
    """Reuse a caller's open session, or open a fresh transactional scope.

    Lets list-building reuse one session for all members instead of opening a nested
    ``session_scope`` per row (which exhausts the connection pool and hangs the request).
    """
    if session is not None:
        yield session
    else:
        with session_scope() as own:
            yield own


def _in_network_npis(session, plan_id: str | None) -> set[str] | None:
    if not plan_id:
        return None
    return set(
        session.execute(
            select(PlanNetwork.npi).where(
                PlanNetwork.plan_id == plan_id, PlanNetwork.in_network.is_(True)
            )
        ).scalars()
    )


def provider_lookup_by_name(
    name: str,
    plan_id: str | None = None,
    limit: int = 3,
    session: Session | None = None,
) -> ProviderSearchOutput:
    """Find providers whose name matches ``name``, scoped to the plan network when known.

    Used to answer follow-ups about a specific recommended provider ("tell me about
    Alan Rosenberg"). Returns at most ``limit`` matches, in-network first when a plan is
    given. Marks ``providers`` missing when nothing matches so the caller can fall through.
    Pass ``session`` to reuse an open session instead of opening a nested one.
    """
    out = ProviderSearchOutput()
    cleaned = name.strip()
    if not cleaned:
        out.mark_missing("providers")
        return out
    with _session_for(session) as session:
        in_network_npis = _in_network_npis(session, plan_id)
        stmt = select(Provider).where(Provider.name.ilike(f"%{cleaned}%"))
        if in_network_npis is not None:
            stmt = stmt.where(Provider.npi.in_(in_network_npis or {"__no_in_network_npi__"}))
        rows = session.execute(stmt.order_by(Provider.name).limit(limit)).scalars().all()
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


def provider_search(
    inp: ProviderSearchInput, session: Session | None = None
) -> ProviderSearchOutput:
    """Search in-network providers by specialty/state.

    Pass ``session`` to reuse an open session (e.g. when called per-row while building a
    member list) instead of opening a nested ``session_scope`` per call.
    """
    out = ProviderSearchOutput()
    with _session_for(session) as session:
        stmt = select(Provider)
        in_network_npis = _in_network_npis(session, inp.plan_id)
        if in_network_npis is not None:
            stmt = stmt.where(Provider.npi.in_(in_network_npis or {"__no_in_network_npi__"}))
        if inp.specialty:
            stmt = stmt.where(Provider.specialty.ilike(f"%{inp.specialty}%"))
        else:
            stmt = stmt.where(Provider.specialty.is_not(None))
        if inp.state:
            stmt = stmt.where(Provider.state == inp.state.upper())
        if inp.accepting_new is not None:
            stmt = stmt.where(Provider.accepting_new.is_(inp.accepting_new))
        rows = session.execute(stmt.order_by(Provider.name).limit(inp.limit)).scalars().all()
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

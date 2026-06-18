"""NPPES ingest: load providers + a synthetic plan_network join.

Two paths:
  1. Real NPPES monthly file at settings.nppes_file — filter to configured states &
     relevant taxonomies, cap at settings.nppes_max_providers.
  2. Deterministic synthetic providers when the file is absent.

Then mark a subset in-network for each plan (the synthetic plan_network table).
Idempotent upserts throughout.
"""

from __future__ import annotations

import csv
import os
import random

from carenav.config import settings
from carenav.data import plans
from carenav.data.db import pg_upsert as _upsert
from carenav.data.db import session_scope
from carenav.data.models import PlanNetwork, Provider

_SEED = 7

# Name/street fragments for the synthetic-provider fallback (used only when the NPPES file
# is absent). Kept local here — providers are not Synthea patients.
_PROVIDER_FIRST = [
    "Jordan", "Avery", "Casey", "Riley", "Morgan", "Taylor", "Jamie", "Quinn",
    "Cameron", "Drew", "Skyler", "Reese", "Hayden", "Rowan", "Emerson", "Finley",
]
_PROVIDER_STREETS = ["Maple Ave", "Oak St", "Washington Blvd", "Park Pl", "Hudson St", "Grove Ln"]

# Taxonomy/specialty pairs the demo cares about (provider-search intents).
_SPECIALTIES = [
    ("207RE0101X", "Endocrinology"),
    ("207RC0000X", "Cardiology"),
    ("208000000X", "Pediatrics"),
    ("207Q00000X", "Family Medicine"),
    ("207RX0202X", "Oncology"),
    ("2084N0400X", "Neurology"),
    ("207W00000X", "Ophthalmology"),
    ("208600000X", "Surgery"),
]
_CITIES = [("Jersey City", "NJ", "07302"), ("Newark", "NJ", "07102"), ("New York", "NY", "10001")]
_PROVIDER_LAST = [
    "Reyes", "Cho", "Bianchi", "Adeyemi", "Larsen", "Mehta", "Donnelly", "Sato",
    "Vasquez", "Friedman", "Owens", "Pereira", "Haddad", "Castro", "Yamamoto",
]


def _generate_synthetic(n: int) -> list[dict]:
    rng = random.Random(_SEED)
    rows: list[dict] = []
    states = [s.strip() for s in settings.nppes_states.split(",") if s.strip()]
    for i in range(n):
        tax, spec = rng.choice(_SPECIALTIES)
        city, state, zip_ = rng.choice([c for c in _CITIES if c[1] in states] or _CITIES)
        rows.append({
            "npi": f"{1000000000 + i}",
            "name": f"Dr. {rng.choice(_PROVIDER_FIRST)} {rng.choice(_PROVIDER_LAST)}",
            "taxonomy": tax,
            "specialty": spec,
            "address": f"{rng.randint(1, 999)} {rng.choice(_PROVIDER_STREETS)}",
            "city": city,
            "state": state,
            "postal_code": zip_,
            "accepting_new": rng.random() > 0.3,
        })
    return rows


def _have_real_file() -> bool:
    return os.path.isfile(settings.nppes_file)


def _parse_real_file(n_max: int) -> list[dict]:
    """Parse the NPPES monthly CSV. Field names are the official NPPES headers."""
    keep_states = {s.strip().upper() for s in settings.nppes_states.split(",") if s.strip()}
    tax_to_spec = {t: s for t, s in _SPECIALTIES}
    rows: list[dict] = []
    with open(settings.nppes_file, newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            if len(rows) >= n_max:
                break
            state = (
                row.get("Provider Business Practice Location Address State Name") or ""
            ).upper()
            if keep_states and state not in keep_states:
                continue
            tax = row.get("Healthcare Provider Taxonomy Code_1", "")
            specialty = tax_to_spec.get(tax)
            if not specialty:
                continue
            org = row.get("Provider Organization Name (Legal Business Name)", "").strip()
            first = row.get("Provider First Name", "").strip()
            last = row.get("Provider Last Name (Legal Name)", "").strip()
            name = org or f"{first} {last}".strip()
            if not name:
                continue
            rows.append({
                "npi": row.get("NPI", ""),
                "name": name,
                "taxonomy": tax,
                "specialty": specialty,
                "address": row.get("Provider Business Practice Location Address Line 1", ""),
                "city": row.get("Provider Business Practice Location Address City Name", ""),
                "state": state,
                "postal_code": (
                    row.get("Provider Business Practice Location Address Postal Code") or ""
                )[:5],
                "accepting_new": True,
            })
    return rows


def run() -> dict[str, int]:
    """Ingest providers + build plan_network. Returns row counts."""
    n_max = settings.nppes_max_providers
    if _have_real_file():
        providers = _parse_real_file(n_max)
        source = "nppes-file"
        if not providers:  # file present but no rows matched filters
            providers = _generate_synthetic(min(n_max, 300))
            source = "nppes-file-empty->synthetic"
    else:
        providers = _generate_synthetic(min(n_max, 300))
        source = "synthetic-fallback"

    # Build a synthetic plan_network: ~60% of providers in-network per plan.
    rng = random.Random(_SEED)
    network_rows: list[dict] = []
    for p in plans.PLANS:
        for prov in providers:
            if rng.random() < 0.6:
                network_rows.append(
                    {"plan_id": p["plan_id"], "npi": prov["npi"], "in_network": True}
                )

    with session_scope() as session:
        _upsert(session, Provider, providers, ["npi"])
        _upsert(session, PlanNetwork, network_rows, ["plan_id", "npi"])

    return {"providers": len(providers), "plan_network": len(network_rows), "_source": source}  # type: ignore[dict-item]


if __name__ == "__main__":
    print(run())

"""Synthea ingest: load plans, members, accumulators, claims, conditions into Postgres.

Real Synthea only. The pipeline reads the CSV export produced by `scripts/run_synthea.sh`
(patients / encounters / conditions) from settings.synthea_output_dir and loads it into
Postgres. If the CSVs are absent, ingest fails with a clear message telling you to run
Synthea first.

CareNav's plan constructs (plans, plan assignment, accumulators) and the condition→KB
mapping live in carenav.data.plans. Synthea models patients; CareNav layers the plans on top.

Idempotent: uses upsert semantics so re-running keeps row counts stable.
"""

from __future__ import annotations

import csv
import os
from datetime import date

from carenav.config import settings
from carenav.data import condition_topics, plans
from carenav.data.db import pg_upsert as _upsert
from carenav.data.db import session_scope
from carenav.data.models import Accumulator, Claim, Condition, Member, Plan


class SyntheaCSVMissing(RuntimeError):
    """Raised when the real Synthea CSV export is not present."""


def _load_plans(session) -> int:
    rows = [
        {
            "plan_id": p["plan_id"],
            "name": p["name"],
            "deductible": p["deductible"],
            "oop_max": p["oop_max"],
            "coinsurance": p["coinsurance"],
        }
        for p in plans.PLANS
    ]
    _upsert(session, Plan, rows, ["plan_id"])
    return len(rows)


def _csv_path(name: str) -> str:
    return os.path.join(settings.synthea_output_dir, name)


def _have_real_csv() -> bool:
    return os.path.isfile(_csv_path("patients.csv"))


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _to_float(s: str) -> float:
    try:
        return float(s or 0)
    except ValueError:
        return 0.0


def _ingest_from_csv(session) -> dict[str, int]:
    """Load members (patients.csv), claims (encounters.csv), conditions (conditions.csv).

    Synthea has no insurance-plan model, so each patient is assigned a CareNav plan
    round-robin and an accumulator is derived from their claim activity. Claims come from
    encounters (which carry TOTAL_CLAIM_COST + PAYER_COVERAGE); conditions are SNOMED-coded
    and classified into KB topics via condition_topics.topic_for (every clinical diagnosis
    maps to a topic; social/administrative findings map to None).
    """
    # --- members (patients.csv) ---
    members: list[dict] = []
    plan_of: dict[str, str] = {}
    member_ids: set[str] = set()
    with open(_csv_path("patients.csv"), newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            mid = (row.get("Id") or f"M{i:06d}").strip()
            name = f"{row.get('FIRST', '').strip()} {row.get('LAST', '').strip()}".strip()
            dob = _parse_date(row.get("BIRTHDATE", "")) or date(1980, 1, 1)
            addr = ", ".join(
                p for p in [row.get("ADDRESS", ""), row.get("CITY", ""),
                            row.get("STATE", ""), row.get("ZIP", "")] if p
            )
            death = _parse_date(row.get("DEATHDATE", ""))
            plan_id = plans.assign_plan(i)
            plan_of[mid] = plan_id
            member_ids.add(mid)
            members.append({
                "member_id": mid,
                "name": name or f"Member {i}",
                "dob": dob,
                "address": addr or "Unknown",
                "plan_id": plan_id,
                # Deceased patients are marked inactive; everyone else is active.
                "eligibility_status": "inactive" if death else "active",
                "coverage_start": plans.coverage_start(),
                "coverage_end": death,
            })

    # --- claims (encounters.csv) ---
    # Each encounter becomes a claim: billed = TOTAL_CLAIM_COST, paid = PAYER_COVERAGE,
    # member_responsibility = billed - paid. Service code is the encounter procedure code.
    claims: list[dict] = []
    enc_path = _csv_path("encounters.csv")
    if os.path.isfile(enc_path):
        with open(enc_path, newline="", encoding="utf-8") as f:
            for j, row in enumerate(csv.DictReader(f)):
                mid = (row.get("PATIENT") or "").strip()
                if mid not in member_ids:
                    continue
                billed = round(_to_float(row.get("TOTAL_CLAIM_COST", "")), 2)
                paid = round(_to_float(row.get("PAYER_COVERAGE", "")), 2)
                resp = round(max(billed - paid, 0.0), 2)
                claims.append({
                    "claim_id": (row.get("Id") or f"CLM-{j}").strip(),
                    "member_id": mid,
                    "provider_npi": (row.get("PROVIDER") or None),
                    "service_code": (row.get("CODE") or "").strip() or "unknown",
                    "billed": billed,
                    "allowed": billed,
                    "paid": paid,
                    "member_responsibility": resp,
                    "status": "paid" if paid > 0 or billed == 0 else "patient_responsibility",
                    "denial_reason": None,
                })

    # --- accumulators: derive year-to-date member responsibility, capped at OOP max ---
    resp_by_member: dict[str, float] = {}
    for c in claims:
        resp_by_member[c["member_id"]] = resp_by_member.get(c["member_id"], 0.0) + c[
            "member_responsibility"
        ]
    accs: list[dict] = []
    for mid in member_ids:
        plan = plans.plan_by_id(plan_of[mid]) or {}
        oop_max = float(plan.get("oop_max", 0) or 0)
        deductible = float(plan.get("deductible", 0) or 0)
        spent = round(resp_by_member.get(mid, 0.0), 2)
        oop_met = round(min(spent, oop_max), 2) if oop_max else spent
        ded_met = round(min(spent, deductible), 2) if deductible else spent
        accs.append({
            "member_id": mid,
            "plan_year": plans.PLAN_YEAR,
            "deductible_met": ded_met,
            "oop_met": oop_met,
        })

    # --- conditions (conditions.csv), SNOMED-coded, linked to KB topics where matched ---
    conditions: list[dict] = []
    seen_cond: set[tuple[str, str]] = set()
    cond_path = _csv_path("conditions.csv")
    if os.path.isfile(cond_path):
        with open(cond_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                mid = (row.get("PATIENT") or "").strip()
                if mid not in member_ids:
                    continue
                code = (row.get("CODE") or "").strip()
                display = (row.get("DESCRIPTION") or "").strip()
                key = (mid, code)
                if not code or key in seen_cond:
                    continue
                seen_cond.add(key)
                stop = (row.get("STOP") or "").strip()
                conditions.append({
                    "member_id": mid,
                    "icd10": code,  # Synthea uses SNOMED; stored in the code column as-is.
                    "display": display or code,
                    "clinical_status": "resolved" if stop else "active",
                    "onset_date": _parse_date(row.get("START", "")),
                    # Classify into a clinical KB topic; None for social/admin findings.
                    "kb_topic": condition_topics.topic_for(display),
                })

    _upsert(session, Member, members, ["member_id"])
    _upsert(session, Accumulator, accs, ["member_id", "plan_year"])
    _upsert(session, Claim, claims, ["claim_id"])
    _upsert(session, Condition, conditions, ["member_id", "icd10"])
    return {
        "members": len(members),
        "accumulators": len(accs),
        "claims": len(claims),
        "conditions": len(conditions),
    }


def run() -> dict[str, int]:
    """Ingest real Synthea CSV data into Postgres. Returns row counts per table."""
    if not _have_real_csv():
        raise SyntheaCSVMissing(
            f"No Synthea CSV export found in {settings.synthea_output_dir!r}. "
            "Generate it first: `bash scripts/run_synthea.sh` (requires Java), then re-run."
        )
    with session_scope() as session:
        n_plans = _load_plans(session)
        counts = _ingest_from_csv(session)
    counts["plans"] = n_plans
    counts["_source"] = "synthea-csv"  # type: ignore[assignment]
    return counts


if __name__ == "__main__":
    print(run())

"""CareNav plan constructs.

Real Synthea generates *patients* (demographics, encounters, conditions, claims) but does
not model CareNav's insurance plans or accumulators. Those are CareNav demo constructs and
live here so the data pipeline can assign each real Synthea patient a plan and derive
accumulators. Condition→KB topic classification lives in carenav.data.condition_topics.

This module is import-only data + small pure helpers — no patient fabrication.
"""

from __future__ import annotations

from datetime import date

PLAN_YEAR = 2026

# The three demo plans. Members are assigned one of these on ingest.
PLANS = [
    {"plan_id": "PLN-BRONZE", "name": "CareNav Bronze",
     "deductible": 4000, "oop_max": 8000, "coinsurance": 0.40},
    {"plan_id": "PLN-SILVER", "name": "CareNav Silver",
     "deductible": 2500, "oop_max": 6000, "coinsurance": 0.30},
    {"plan_id": "PLN-GOLD", "name": "CareNav Gold",
     "deductible": 1000, "oop_max": 4000, "coinsurance": 0.20},
]

_PLAN_CYCLE: list[str] = [str(p["plan_id"]) for p in PLANS]


def assign_plan(index: int) -> str:
    """Deterministically assign a plan id to the nth member (round-robin across PLANS)."""
    return _PLAN_CYCLE[index % len(_PLAN_CYCLE)]


def plan_by_id(plan_id: str) -> dict | None:
    for p in PLANS:
        if p["plan_id"] == plan_id:
            return p
    return None


def coverage_start() -> date:
    return date(PLAN_YEAR, 1, 1)


# --- condition → KB topic mapping --------------------------------------------------------
#
# Conditions are classified into KB topics by carenav.data.condition_topics, which covers
# every clinical Synthea diagnosis. This module owns only the plan constructs.


__all__ = [
    "PLAN_YEAR",
    "PLANS",
    "assign_plan",
    "plan_by_id",
    "coverage_start",
]

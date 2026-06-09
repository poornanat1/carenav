"""Tests for carenav.data.plans — the CareNav plan constructs and condition→KB mapping
that survive the (now real-Synthea-only) data pipeline. No DB or network required."""

from carenav.data import plans


def test_plans_present():
    assert {p["plan_id"] for p in plans.PLANS} == {"PLN-BRONZE", "PLN-SILVER", "PLN-GOLD"}


def test_assign_plan_is_round_robin_and_deterministic():
    assigned = [plans.assign_plan(i) for i in range(6)]
    assert assigned[:3] == [p["plan_id"] for p in plans.PLANS]
    assert assigned[3:] == assigned[:3]  # cycles


def test_plan_by_id():
    assert plans.plan_by_id("PLN-GOLD")["name"] == "CareNav Gold"
    assert plans.plan_by_id("PLN-UNKNOWN") is None

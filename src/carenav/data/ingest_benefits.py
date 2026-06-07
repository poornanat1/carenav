"""Benefit-rule ingest: load the hand-authored seed (the one hand-built artifact).

Reads carenav/data/seeds/benefit_rules.json and upserts BenefitRule rows. Idempotent.
"""

from __future__ import annotations

import json

from carenav.config import settings
from carenav.data.db import pg_upsert, session_scope
from carenav.data.models import BenefitRule


def run() -> dict[str, int]:
    with open(settings.benefit_rules_seed, encoding="utf-8") as f:
        seed = json.load(f)

    rows: list[dict] = []
    for plan_block in seed["rules"]:
        plan_id = plan_block["plan_id"]
        for item in plan_block["items"]:
            rows.append({
                "plan_id": plan_id,
                "key": item["key"],
                "is_category": item.get("is_category", False),
                "covered": item.get("covered", True),
                "copay": item.get("copay"),
                "coinsurance": item.get("coinsurance"),
                "prior_auth_required": item.get("prior_auth_required", False),
                "notes": item.get("notes"),
            })

    with session_scope() as session:
        pg_upsert(session, BenefitRule, rows, ["plan_id", "key"])

    return {"benefit_rules": len(rows)}


if __name__ == "__main__":
    print(run())

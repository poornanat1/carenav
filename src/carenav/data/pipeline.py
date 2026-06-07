"""Data pipeline entrypoint: `python -m carenav.data.pipeline` (a.k.a. `make data`).

Runs each ingest stage idempotently, then asserts row counts so a fresh clone
reproduces the dataset. Re-running must not duplicate rows or change asserted counts.

Stages:
  synthea  -> plans, members, accumulators, claims
  nppes    -> providers, plan_network
  benefits -> benefit_rules
  kb       -> KB corpus + embeddings
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from carenav.data import ingest_benefits, ingest_nppes, ingest_synthea
from carenav.data.db import healthcheck, init_schema, session_scope
from carenav.data.models import (
    Accumulator,
    BenefitRule,
    Claim,
    Condition,
    Member,
    Plan,
    PlanNetwork,
    Provider,
)
from carenav.rag import ingest_kb
from carenav.rag.models import KBChunk, KBDoc  # registers KB tables on Base for init_schema

STAGES = ["synthea", "nppes", "benefits", "kb"]

# Minimum expected counts after a successful run. Asserted so the dataset is sane.
# Member/claim/condition counts come from real Synthea and vary run to run (the living
# population export fluctuates), so these are floors, not exact targets.
MIN_COUNTS = {
    "plan": 3,
    "member": 20,        # real Synthea NJ export (varies; typically 50-100+)
    "accumulator": 20,
    "claim": 1,          # one per Synthea encounter
    "condition": 1,      # real SNOMED-coded diagnoses
    "provider": 50,
    "plan_network": 50,
    "benefit_rule": 18,  # 3 plans x 6 categories
    "kb_doc": 55,        # 31 consumer-health + 26 drug-label + 4 SBC/coverage
    "kb_chunk": 200,     # heading-scoped chunks across the corpus
}

_MODEL_BY_TABLE = {
    "plan": Plan,
    "member": Member,
    "accumulator": Accumulator,
    "claim": Claim,
    "condition": Condition,
    "provider": Provider,
    "plan_network": PlanNetwork,
    "benefit_rule": BenefitRule,
    "kb_doc": KBDoc,
    "kb_chunk": KBChunk,
}


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def current_counts() -> dict[str, int]:
    with session_scope() as session:
        return {name: _count(session, model) for name, model in _MODEL_BY_TABLE.items()}


def assert_counts(counts: dict[str, int]) -> list[str]:
    """Return a list of failures (empty == all good)."""
    failures = []
    for table, minimum in MIN_COUNTS.items():
        got = counts.get(table, 0)
        if got < minimum:
            failures.append(f"  ✗ {table}: expected >= {minimum}, got {got}")
    return failures


def run_kb() -> dict[str, int]:
    # KB corpus + embeddings: corpus -> chunk -> embed -> pgvector. Idempotent.
    return ingest_kb.run()


def run(stages: list[str]) -> int:
    if not healthcheck():
        print(
            "ERROR: cannot reach the database. Is Postgres up? Try `make db-up`.",
            file=sys.stderr,
        )
        return 2

    print("→ init schema (tables + pgvector extension)")
    init_schema()

    if "synthea" in stages:
        print("→ stage: synthea")
        print("   ", ingest_synthea.run())
    if "nppes" in stages:
        print("→ stage: nppes")
        print("   ", ingest_nppes.run())
    if "benefits" in stages:
        print("→ stage: benefits")
        print("   ", ingest_benefits.run())
    if "kb" in stages:
        print("→ stage: kb")
        print("   ", run_kb())

    print("\n→ verifying row counts")
    counts = current_counts()
    for table, n in counts.items():
        print(f"    {table:14s} {n}")

    failures = assert_counts(counts)
    if failures:
        print("\nROW-COUNT ASSERTIONS FAILED:")
        print("\n".join(failures))
        return 1

    print("\n✅ data pipeline complete — all row-count assertions passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CareNav data pipeline")
    parser.add_argument(
        "--only",
        choices=STAGES,
        help="Run a single stage instead of all.",
    )
    args = parser.parse_args(argv)
    stages = [args.only] if args.only else STAGES
    return run(stages)


if __name__ == "__main__":
    raise SystemExit(main())

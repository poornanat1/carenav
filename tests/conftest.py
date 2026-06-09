"""Test-wide config — set BEFORE any carenav import (conftest is collected first).

CareNav runs on **Postgres everywhere** (pgvector + the hybrid_search full-text function).
Tests run against the configured DATABASE_URL — the docker-compose pgvector service by
default. `requires_db` skips DB-backed tests cleanly when Postgres is unreachable (so
pure-logic tests still run anywhere); `requires_mistral` / `requires_generation` skip the
real-Mistral paths when no key/quota is configured.
"""

from __future__ import annotations

import functools
import os

# Default to the docker-compose pgvector service (host port 5433 per the dev override).
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://carenav:carenav@localhost:5433/carenav"
)

import pytest  # noqa: E402

from carenav.config import settings  # noqa: E402


@functools.lru_cache(maxsize=1)
def _db_reachable() -> bool:
    try:
        from carenav.data.db import healthcheck

        return healthcheck()
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(), reason="needs a reachable Postgres (docker compose up db)"
)


def _has_mistral() -> bool:
    return bool(settings.mistral_api_key)


requires_mistral = pytest.mark.skipif(not _has_mistral(), reason="needs a MISTRAL_API_KEY")


@functools.lru_cache(maxsize=1)
def _can_generate() -> bool:
    """Probe whether the configured key actually has chat (generation) quota.

    Cached so the probe costs at most one call per session; the agent tests use real
    generation per the project decision, so they skip cleanly if generation is unavailable.
    """
    if not _has_mistral():
        return False
    try:
        from carenav.models import ModelGateway

        ModelGateway(capture_prompts=False).generate("ping", label="probe")
        return True
    except Exception:
        return False


requires_generation = pytest.mark.skipif(
    not _can_generate(), reason="key has no chat/generation quota"
)

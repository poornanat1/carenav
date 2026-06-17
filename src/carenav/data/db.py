"""Database engine, session factory, and schema initialization.

Single source of the SQLAlchemy engine. The pgvector extension is created here so the
RAG embedding column can be defined later without a separate migration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from carenav.config import settings
from carenav.data.models import Base

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _normalize_url(url: str) -> str:
    """Coerce a bare ``postgresql://`` URL (as managed hosts like Render emit) to the
    ``postgresql+psycopg://`` driver the app uses. URLs that already name a driver are
    left untouched."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            _normalize_url(settings.database_url), pool_pre_ping=True, future=True
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session scope: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_postgres() -> None:
    """Guard: CareNav is Postgres-only (pgvector + full-text hybrid retrieval)."""
    dialect = get_engine().dialect.name
    if dialect != "postgresql":
        raise RuntimeError(
            f"CareNav requires PostgreSQL; got '{dialect}'. Set DATABASE_URL to a "
            "postgresql+psycopg URL (the docker-compose pgvector service)."
        )


def pg_upsert(session, model, rows: list[dict], index_elements: list[str]) -> None:
    """Idempotent bulk upsert via INSERT ... ON CONFLICT DO UPDATE.

    Batched to stay under Postgres's 65535 bind-parameter limit (cols x rows). The shared
    ingest helper for every loader (Synthea, NPPES, benefits, KB).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not rows:
        return
    n_cols = max(1, len(model.__table__.columns))
    batch = max(1, 60000 // n_cols)
    for start in range(0, len(rows), batch):
        chunk = rows[start:start + batch]
        stmt = pg_insert(model).values(chunk)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in model.__table__.columns
            if c.name not in index_elements and c.name != "id"
        }
        stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)
        session.execute(stmt)


def ensure_extensions() -> None:
    """Create the pgvector extension."""
    require_postgres()
    with get_engine().begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def init_schema(drop: bool = False) -> None:
    """Create all tables, the pgvector extension, and SQL functions. Idempotent."""
    ensure_extensions()
    engine = get_engine()
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _install_sql_functions()


def _install_sql_functions() -> None:
    """Install the repo's .sql files (e.g. hybrid_search) — idempotent.

    The retrieval policy lives consolidated in carenav/rag/sql/hybrid_search.sql; Python
    callers stay thin. CREATE OR REPLACE / IF NOT EXISTS keep re-runs safe.
    """
    from pathlib import Path

    sql_dir = Path(__file__).resolve().parent.parent / "rag" / "sql"
    with get_engine().begin() as conn:
        for path in sorted(sql_dir.glob("*.sql")):
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))


def healthcheck() -> bool:
    """Return True if the DB is reachable."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

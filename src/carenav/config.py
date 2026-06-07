"""Central configuration for CareNav.

All settings load from environment variables (or a local .env). Nothing else in the
codebase should read os.environ directly — import `settings` from here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Package root (…/src/carenav). Packaged resources (e.g. the benefit-rule seed) resolve
# against this, not the process CWD, so the pipeline runs from any working directory.
_PKG_DIR = Path(__file__).resolve().parent
_SEED_DEFAULT = str(_PKG_DIR / "data" / "seeds" / "benefit_rules.json")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # No env prefix: vars are bare (DATABASE_URL, GOOGLE_API_KEY, ...). Note this means
        # a same-named var already in the environment/CI will be picked up.
        env_prefix="",
        extra="ignore",
    )

    # --- environment ---
    env: str = Field(default="local", description="local | ci | prod")

    # --- database (Postgres + pgvector) ---
    # Default points at the docker-compose service.
    database_url: str = Field(
        default="postgresql+psycopg://carenav:carenav@localhost:5432/carenav",
        description="SQLAlchemy URL for Postgres (pgvector enabled).",
    )

    # --- data pipeline paths ---
    data_dir: str = Field(
        default="./data_artifacts", description="Root for downloaded/generated data."
    )
    synthea_output_dir: str = Field(default="./data_artifacts/synthea/csv")
    nppes_file: str = Field(default="./data_artifacts/nppes/npidata.csv")
    benefit_rules_seed: str = Field(default=_SEED_DEFAULT)

    # Keep the demo dataset small & reproducible.
    synthea_population: int = Field(default=200, description="Synthea patient count to generate.")
    nppes_max_providers: int = Field(default=5000, description="Cap providers loaded from NPPES.")
    nppes_states: str = Field(default="NJ,NY", description="Comma-separated states to keep.")

    # --- models (Mistral default; gateway stays provider-agnostic) ---
    model_provider: str = Field(default="mistral", description="mistral | google | anthropic")
    model_small: str = Field(
        default="mistral-small-latest", description="Tier 1 small/cheap model."
    )
    model_frontier: str = Field(
        default="mistral-large-latest", description="Tier 2 frontier model."
    )

    # Force the gateway's offline stub for *generation* even when a Mistral credential is
    # present. Embeddings are unaffected (always real). Useful when a credential has
    # embedding quota but no chat quota, or to run the loop without spend.
    stub_generation: bool = Field(default=False, description="Use the stub generator only.")

    # Per-million-token prices (USD) for cost capture in the gateway. Keyed by model name;
    # the gateway falls back to the small-tier price for any unlisted model. Update as
    # pricing changes — these feed the cost/conversation metric in the eval.
    model_request_timeout_s: float = Field(default=30.0, description="Per model call timeout.")

    # Reaching Mistral — a single API key (from https://console.mistral.ai/) is REQUIRED
    # (embeddings are always real). It serves both chat generation and embeddings.
    mistral_api_key: str | None = Field(
        default=None, description="Mistral API key (from console.mistral.ai)."
    )

    # --- embeddings / vector store ---
    # mistral-embed is Mistral's embedding model: a fixed 1024-dim symmetric embedding
    # (no asymmetric task types, no dimension truncation). embedding_dim must match its
    # native 1024 so the vector fits the pgvector column (see carenav/rag/embeddings.py).
    embedding_model: str = Field(default="mistral-embed")
    embedding_dim: int = Field(default=1024, description="Vector dimension for pgvector column.")
    rag_top_k: int = Field(default=5)
    # Relevance-gap prune: after the top-k search, drop docs whose best chunk scores more
    # than this RELATIVE fraction below the top hit (e.g. 0.05 = a 5% score drop from the
    # top). Keeps a query's own tightly-scored cluster (e.g. a named drug's chunks) and
    # prunes generic neighbors that sit a clear gap below, so the generator isn't handed
    # weakly-relevant chunks it might cite. 0 disables the prune.
    rag_relevance_margin: float = Field(default=0.045)
    # Hybrid retrieval: weight of the lexical ts_rank term added to cosine similarity in
    # hybrid_search.sql. Embeddings blur named entities (Gold vs Silver plan, drug names);
    # the weighted ts_rank (title A ≫ body D) re-anchors them. Calibrated so a title match
    # (~0.5-0.7 rank) adds ~0.05-0.07 — decisive between sibling docs, but small against
    # real topical gaps. 0 = pure vector search.
    rag_lex_weight: float = Field(default=0.1)

    # --- orchestrator ---
    max_steps: int = Field(default=5, description="Bound on plan/tool_exec/reflect loop.")

    # --- escalation thresholds (swept in eval) ---
    tau_low: float = Field(default=0.6, description="Confidence bar for non-urgent turns.")
    tau_high: float = Field(default=0.8, description="Confidence bar for urgent turns.")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

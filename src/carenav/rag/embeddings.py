"""Embeddings — always real Mistral, delegated to the ModelGateway.

CareNav embeds with `mistral-embed` via the gateway (the only place a provider SDK is
imported, docs/02). A Mistral API key backs `make data` and every retrieval, so embeddings
are always real. `mistral-embed` produces a fixed 1024-dim vector matching the pgvector
column (`settings.embedding_dim`).

`mistral-embed` is a single symmetric model: corpus chunks and queries are embedded
identically (no asymmetric document/query task types), so embed_texts/embed_query differ
only in batch shape.
"""

from __future__ import annotations

_gateway = None


def _get_gateway(gateway=None):
    """Use the caller's gateway if given (so its ledger captures the cost); else a shared
    module-level one for corpus-side embedding (ingest), where there is no turn ledger."""
    if gateway is not None:
        return gateway
    global _gateway
    if _gateway is None:
        from carenav.models import ModelGateway

        # Corpus-side embedding; no need to capture prompts for the PII-leak sweep.
        _gateway = ModelGateway(capture_prompts=False)
    return _gateway


def backend_name() -> str:
    return _get_gateway().backend_name()


def embed_texts(texts: list[str], gateway=None) -> list[list[float]]:
    """Embed a batch of corpus documents into `settings.embedding_dim`-length vectors."""
    if not texts:
        return []
    return _get_gateway(gateway).embed(texts)


def embed_query(text: str, gateway=None) -> list[float]:
    """Embed a single query string (same symmetric model as corpus documents)."""
    return _get_gateway(gateway).embed([text])[0]

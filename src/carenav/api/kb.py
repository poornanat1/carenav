"""Serve internal KB corpus documents (the vendored markdown) to the UI.

Some KB docs are internal/synthetic (the CareNav SBC plans and coverage explainers).
Their citations shouldn't link out to a generic external page — instead the UI fetches
the doc body here and renders the markdown in-app. The corpus on disk is the source of
truth (see carenav/rag/corpus/README.md), so we read it directly rather than
reconstructing the body from KB chunks.
"""

from __future__ import annotations

from functools import lru_cache

from carenav.rag.corpus_loader import SourceDoc, load_corpus


@lru_cache(maxsize=1)
def _doc_index() -> dict[str, SourceDoc]:
    return {doc.doc_id: doc for doc in load_corpus()}


def doc_id_for_chunk(chunk_id: str) -> str | None:
    """KB chunk ids are '{doc_id}::{ordinal}'. Tool/profile citations have no KB doc."""
    if chunk_id.startswith("tool:"):
        return None
    doc_id, sep, _ = chunk_id.partition("::")
    return doc_id if sep else None


def corpus_source_url(chunk_id: str) -> str | None:
    """The corpus-of-record source_url for a citation's doc, or None for internal docs.

    The on-disk corpus is authoritative for whether a doc is internal — so a citation
    renders as internal/in-app even if the live DB still holds a stale external URL from
    an older ingest.
    """
    doc_id = doc_id_for_chunk(chunk_id)
    if not doc_id:
        return None
    doc = _doc_index().get(doc_id)
    return doc.source_url if doc else None


def is_known_doc(chunk_id: str) -> bool:
    doc_id = doc_id_for_chunk(chunk_id)
    return bool(doc_id and doc_id in _doc_index())


def kb_doc(doc_id: str) -> dict | None:
    """Return the markdown body + metadata for one corpus doc, or None if unknown."""
    doc = _doc_index().get(doc_id)
    if not doc:
        return None
    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "source_type": doc.source_type,
        "source_url": doc.source_url or None,
        "last_reviewed": doc.last_reviewed,
        "body": doc.body,
    }

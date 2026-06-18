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

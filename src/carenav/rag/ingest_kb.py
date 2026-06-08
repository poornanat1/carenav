"""KB ingest: corpus -> chunk -> embed -> pgvector. Idempotent; returns counts.

This is the `kb` stage of the data pipeline. It loads the vendored corpus
(carenav/rag/corpus/), chunks each doc heading-scoped, embeds the chunks with real
Mistral embeddings (a MISTRAL_API_KEY backs this stage), and upserts KBDoc + KBChunk rows.
Re-running does not duplicate rows: chunk ids are stable per (doc, ordinal) and stale
chunks from a re-chunk are deleted first.

Run standalone:  python -m carenav.rag.ingest_kb
Via pipeline:    make data-kb
"""

from __future__ import annotations

from sqlalchemy import delete

from carenav.data.db import pg_upsert as _upsert
from carenav.data.db import session_scope
from carenav.rag import embeddings
from carenav.rag.chunking import chunk_document
from carenav.rag.corpus_loader import SourceDoc, load_corpus
from carenav.rag.models import KBChunk, KBDoc


def _chunk_id(doc_id: str, ordinal: int) -> str:
    return f"{doc_id}::{ordinal:03d}"


def _build_rows(docs: list[SourceDoc]) -> tuple[list[dict], list[dict]]:
    """Return (doc_rows, chunk_rows) with embeddings attached, deterministic order."""
    doc_rows: list[dict] = []
    chunk_specs: list[dict] = []  # rows minus embedding, plus the text to embed
    for doc in docs:
        doc_rows.append({
            "doc_id": doc.doc_id,
            "source_type": doc.source_type,
            "title": doc.title,
            "source_url": doc.source_url,
            "last_reviewed": doc.last_reviewed,
        })
        for ch in chunk_document(doc.body):
            chunk_specs.append({
                "chunk_id": _chunk_id(doc.doc_id, ch.ordinal),
                "doc_id": doc.doc_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "source_url": doc.source_url,
                "last_reviewed": doc.last_reviewed,
                "section_path": ch.section_path,
                "ordinal": ch.ordinal,
                "text": ch.text,
            })

    # Contextual chunk embeddings: embed the chunk WITH its doc title + section path so the
    # vector carries its subject. Without this, generically-worded sections (e.g. every drug
    # doc's "Adverse reactions") embed nearly subject-free and bleed across docs — a
    # "metformin side effects" query would land on another drug's side-effects chunk. The
    # stored text stays unchanged; only the embedded string is contextualized.
    vectors = embeddings.embed_texts(
        [f"{c['title']} — {c['section_path']}\n{c['text']}" for c in chunk_specs]
    )
    chunk_rows = [
        {**spec, "embedding": vec} for spec, vec in zip(chunk_specs, vectors, strict=True)
    ]
    return doc_rows, chunk_rows


def run() -> dict[str, int]:
    docs = load_corpus()
    doc_rows, chunk_rows = _build_rows(docs)
    doc_ids = [d["doc_id"] for d in doc_rows]
    keep_chunk_ids = {c["chunk_id"] for c in chunk_rows}

    with session_scope() as session:
        _upsert(session, KBDoc, doc_rows, ["doc_id"])
        _upsert(session, KBChunk, chunk_rows, ["chunk_id"])
        # Delete chunks that no longer exist for these docs (e.g. after a re-chunk),
        # so re-ingest is a clean replace rather than an accumulate.
        existing = session.execute(
            delete(KBChunk)
            .where(KBChunk.doc_id.in_(doc_ids))
            .where(KBChunk.chunk_id.notin_(keep_chunk_ids))
        )
        _ = existing  # rowcount available if needed

    return {
        "kb_doc": len(doc_rows),
        "kb_chunk": len(chunk_rows),
        "_embeddings": embeddings.backend_name(),  # type: ignore[dict-item]
    }


if __name__ == "__main__":
    print(run())

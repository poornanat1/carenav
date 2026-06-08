"""RAG ORM models: the KB corpus + its vector index.

Lives in carenav/rag (not carenav/data) so the embedding column sits next to the
retrieval code that uses it (docs/08-data-model.md, docs/07-rag.md).

`KBDoc` is one source document (a MedlinePlus page, an openFDA label, an SBC section).
`KBChunk` is one heading-scoped ~512-token slice of a doc, carrying its own embedding
and the citation metadata the grounding contract requires: every factual claim in a
generated answer must cite a chunk id.

The embedding column is pgvector's `Vector`. CareNav runs on Postgres everywhere —
pgvector + full-text retrieval (the hybrid_search function) are core to the design.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from carenav.config import settings
from carenav.data.models import Base

# Source categories used both as KBDoc.source_type and as the per-intent retrieval
# filter (docs/07-rag.md): medication intents only hit drug-label chunks, coverage
# intents only hit SBC chunks, etc. This is a quality AND a safety boundary.
SOURCE_TYPES = ("consumer_health", "drug_label", "sbc")


def _embedding_column():
    """pgvector Vector column, sized to settings.embedding_dim (mistral-embed = 1024)."""
    return mapped_column(Vector(settings.embedding_dim), nullable=True)


class KBDoc(Base):
    __tablename__ = "kb_doc"

    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # one of SOURCE_TYPES
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    last_reviewed: Mapped[str | None] = mapped_column(String, nullable=True)

    chunks: Mapped[list[KBChunk]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )


class KBChunk(Base):
    __tablename__ = "kb_chunk"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("kb_doc.doc_id"), nullable=False)
    # Denormalized from the doc so retrieval can filter/cite without a join.
    source_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    last_reviewed: Mapped[str | None] = mapped_column(String, nullable=True)
    # Heading path of the section this chunk came from, e.g. "Uses > How to take".
    section_path: Mapped[str | None] = mapped_column(String, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = _embedding_column()

    doc: Mapped[KBDoc] = relationship(back_populates="chunks")

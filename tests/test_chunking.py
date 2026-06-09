"""Tests for structure-aware chunking (no DB)."""

from carenav.rag import chunking
from carenav.rag.chunking import chunk_document
from carenav.rag.corpus_loader import load_corpus

_DOC = """# Title

## Section A

Para one of A. It has two sentences here.

Para two of A.

## Section B

Only paragraph of B.
"""


def test_heading_scoped_sections():
    chunks = chunk_document(_DOC)
    paths = {c.section_path for c in chunks}
    assert "Title > Section A" in paths
    assert "Title > Section B" in paths
    # No chunk spans two headings.
    for c in chunks:
        assert " > " in c.section_path


def test_ordinals_are_contiguous():
    chunks = chunk_document(_DOC)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_is_deterministic():
    a = chunk_document(_DOC)
    b = chunk_document(_DOC)
    assert [(c.ordinal, c.section_path, c.text) for c in a] == [
        (c.ordinal, c.section_path, c.text) for c in b
    ]


def test_long_section_splits_with_overlap():
    # A section well over the target should produce more than one chunk.
    sentence = "This is a sentence about coverage and benefits. "
    body = "# T\n\n## Big\n\n" + (sentence * 600)
    chunks = chunk_document(body)
    big = [c for c in chunks if c.section_path == "T > Big"]
    assert len(big) >= 2
    # Each chunk stays within a reasonable band of the word target.
    for c in big:
        assert len(c.text.split()) <= chunking._TARGET_WORDS + chunking._OVERLAP_WORDS + 50


def test_corpus_chunks_nonempty_and_carry_metadata():
    docs = load_corpus()
    assert len(docs) >= 6
    for d in docs:
        chunks = chunk_document(d.body)
        assert chunks, f"{d.doc_id} produced no chunks"
        for c in chunks:
            assert c.text.strip()
            assert c.section_path

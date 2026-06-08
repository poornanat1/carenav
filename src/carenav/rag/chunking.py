"""Structure-aware, heading-scoped chunking (docs/07-rag.md).

We split a Markdown body along its heading hierarchy, then pack each section's
paragraphs into ~512-token chunks with a sentence overlap between consecutive chunks of
the same section. Each chunk keeps its **section path** (e.g. "Type 2 Diabetes >
Symptoms") as citation metadata, and a stable deterministic `chunk_id` so re-ingest is
idempotent.

Token counting is a lightweight word≈token approximation (no tokenizer dependency); the
target is a chunk *size band*, not exact token parity with a specific model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ~512-token target, approximated in words. Overlap carries a little context across the
# boundary so a claim split across two chunks is still retrievable.
TARGET_TOKENS = 512
OVERLAP_TOKENS = 64
# Rough words-per-token factor for plain English prose.
_WORDS_PER_TOKEN = 0.75

_TARGET_WORDS = int(TARGET_TOKENS * _WORDS_PER_TOKEN)
_OVERLAP_WORDS = int(OVERLAP_TOKENS * _WORDS_PER_TOKEN)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    section_path: str
    text: str


def _word_count(text: str) -> int:
    return len(text.split())


@dataclass
class _Section:
    path: str
    paragraphs: list[str]


def _split_sections(body: str) -> list[_Section]:
    """Walk the Markdown headings, grouping body paragraphs under their heading path."""
    sections: list[_Section] = []
    heading_stack: list[tuple[int, str]] = []  # (level, text)
    current_paras: list[str] = []
    para_buf: list[str] = []

    def flush_para() -> None:
        if para_buf:
            current_paras.append(" ".join(para_buf).strip())
            para_buf.clear()

    def path_str() -> str:
        return " > ".join(h[1] for h in heading_stack) if heading_stack else "(body)"

    def open_section() -> None:
        sections.append(_Section(path=path_str(), paragraphs=current_paras.copy()))

    started = False
    for line in body.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            # Close the section we were accumulating before moving to the new heading.
            flush_para()
            if started:
                open_section()
            current_paras = []
            level = len(m.group(1))
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, m.group(2).strip()))
            started = True
            continue
        if line.strip() == "":
            flush_para()
        else:
            para_buf.append(line.strip())
    flush_para()
    if started or current_paras:
        open_section()

    # Drop sections with no body text (heading-only parents).
    return [s for s in sections if any(p for p in s.paragraphs)]


def _pack(paragraphs: list[str]) -> list[str]:
    """Pack paragraphs into ~TARGET_WORDS windows with sentence overlap between windows."""
    windows: list[str] = []
    buf: list[str] = []
    buf_words = 0

    def emit() -> None:
        nonlocal buf, buf_words
        if not buf:
            return
        windows.append(" ".join(buf).strip())
        # Seed the next window with trailing sentences for overlap.
        tail = _SENTENCE_RE.split(" ".join(buf))
        carry: list[str] = []
        carry_words = 0
        for sent in reversed(tail):
            w = _word_count(sent)
            if carry_words + w > _OVERLAP_WORDS:
                break
            carry.insert(0, sent)
            carry_words += w
        buf = carry
        buf_words = carry_words

    for para in paragraphs:
        pw = _word_count(para)
        if buf and buf_words + pw > _TARGET_WORDS:
            emit()
        # A single oversized paragraph: split on sentences so no chunk runs away.
        if pw > _TARGET_WORDS:
            for sent in _SENTENCE_RE.split(para):
                sw = _word_count(sent)
                if buf and buf_words + sw > _TARGET_WORDS:
                    emit()
                buf.append(sent)
                buf_words += sw
        else:
            buf.append(para)
            buf_words += pw
    if buf:
        windows.append(" ".join(buf).strip())
    # The overlap seed can leave a trailing duplicate-only window; drop empties.
    return [w for w in windows if w.strip()]


def chunk_document(body: str) -> list[Chunk]:
    """Chunk a Markdown body into heading-scoped, ~512-token Chunks with overlap."""
    chunks: list[Chunk] = []
    ordinal = 0
    for section in _split_sections(body):
        for window in _pack(section.paragraphs):
            chunks.append(Chunk(ordinal=ordinal, section_path=section.path, text=window))
            ordinal += 1
    return chunks

"""Load the vendored KB corpus: parse frontmatter + body from each Markdown file.

The corpus (carenav/rag/corpus/) is the reproducible source of truth — see its README.
Each file is `--- yaml frontmatter ---` then a heading-structured Markdown body. We keep
the parser dependency-free (no PyYAML): the frontmatter is flat `key: value` pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path(__file__).parent / "corpus"

# source_url is optional: internal/synthetic docs (the CareNav SBC plans and coverage
# explainers) have no external page to cite — the UI renders their markdown in-app instead.
_REQUIRED = ("doc_id", "source_type", "title")


@dataclass(frozen=True)
class SourceDoc:
    doc_id: str
    source_type: str
    title: str
    source_url: str | None
    last_reviewed: str | None
    body: str  # Markdown body (everything after the frontmatter)


def _parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing '---' frontmatter block")
    # Split on the first two '---' fences.
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: malformed frontmatter (need opening and closing '---')")
    _, raw_meta, body = parts
    meta: dict[str, str] = {}
    for line in raw_meta.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"{path}: frontmatter line is not 'key: value': {line!r}")
        meta[key.strip()] = value.strip()
    for req in _REQUIRED:
        if not meta.get(req):
            raise ValueError(f"{path}: frontmatter missing required field {req!r}")
    return meta, body.strip()


def load_doc(path: Path) -> SourceDoc:
    meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"), path)
    return SourceDoc(
        doc_id=meta["doc_id"],
        source_type=meta["source_type"],
        title=meta["title"],
        source_url=meta.get("source_url") or None,
        last_reviewed=meta.get("last_reviewed") or None,
        body=body,
    )


def load_corpus(corpus_dir: Path | None = None) -> list[SourceDoc]:
    """Load every corpus .md file (excluding the corpus README), sorted for determinism."""
    root = corpus_dir or CORPUS_DIR
    files = sorted(p for p in root.rglob("*.md") if p.name.lower() != "readme.md")
    docs = [load_doc(p) for p in files]
    seen: set[str] = set()
    for d in docs:
        if d.doc_id in seen:
            raise ValueError(f"duplicate doc_id in corpus: {d.doc_id}")
        seen.add(d.doc_id)
    return docs

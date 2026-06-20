"""The `[CHUNK:<id>]` citation contract — one source of truth.

Grounded answers cite their evidence inline as ``[CHUNK:<chunk_id>]`` (docs/07). That
format is produced by the prompt builder, emitted by the generator/stub, parsed by the
groundedness check, and read by the agent. Keeping the regex and the formatter here means a
change to the marker shape can't silently desync one of those callers from the others.
"""

from __future__ import annotations

import re

# A citation marker: [CHUNK:<id>] where <id> is any run of non-']' characters. The capture
# group is the chunk id. Chunk ids may be KB ids or tool refs like "tool:member_profile".
CITATION_RE = re.compile(r"\[CHUNK:([^\]]+)\]")

# A run of one or more citation markers with optional surrounding whitespace. Used when
# splitting sentences so trailing citations stay attached to the sentence they support.
CITATION_RUN_RE = re.compile(r"(?:\s*\[CHUNK:[^\]]+\])+")


def format_citation(chunk_id: str) -> str:
    """Render a citation marker for a chunk id."""
    return f"[CHUNK:{chunk_id}]"


def cited_ids(text: str) -> list[str]:
    """Every chunk id cited in text, in order (with duplicates)."""
    return CITATION_RE.findall(text)

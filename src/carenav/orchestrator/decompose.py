"""decompose node — split multi-subject questions into independently-groundable parts.

Fixes the comparative failure mode (probe #26: "lisinopril vs losartan" escalated because
the doc-level retrieval prune keeps the dominant subject's doc, so the second subject's
half of the answer can never be grounded). A comparative is detected deterministically;
the actual split is one small-model call, validated to 2-3 sub-questions; on any doubt we
fall back to the original question unsplit (never worse than today).
"""

from __future__ import annotations

import re

from carenav.models import ModelGateway

_COMPARATIVE = re.compile(
    r"\bvs\.?\b|\bversus\b|\bcompared? (to|with)\b|\bdifference between\b"
    r"|\bwhich is (better|safer)\b",
    re.IGNORECASE,
)

_SPLIT_PROMPT = """Split this comparison question into separate single-subject questions, one per
subject, that together cover what was asked. Keep each question self-contained.

Question: {question}

Reply with one question per line, 2 or 3 lines, nothing else."""


def decompose(question: str, gateway: ModelGateway) -> list[str]:
    """Return sub-questions (>=1). Non-comparatives pass through as [question]."""
    if not _COMPARATIVE.search(question):
        return [question]
    raw = gateway.generate(
        _SPLIT_PROMPT.format(question=question), label="orchestrator.decompose"
    ).text
    subs = [line.strip(" -*\t") for line in raw.splitlines() if line.strip()]
    subs = [s for s in subs if s.endswith("?") or len(s.split()) >= 3][:3]
    return subs if len(subs) >= 2 else [question]

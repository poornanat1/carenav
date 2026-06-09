"""Groundedness check (docs/07-rag.md) — the claim-level half of the grounding contract.

After `generate`, every factual sentence must cite a real chunk id of the form
[CHUNK:<id>]. This module:

  1. Splits the answer into sentences.
  2. Classifies each as a *factual claim* (needs a citation) or not.
  3. Verifies the citation names a chunk that was actually retrieved AND that the cited
     chunk entails the claim (a lightweight lexical-overlap entailment in v1; an
     LLM-judge entailment is a planned upgrade).

Output: which sentences passed, which are uncited/unsupported, and a cleaned answer with
unsupported sentences stripped. The agent decides what to do with the verdict
(regenerate once, then escalate).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from carenav.rag.retrieval import Hit

_CITE_RE = re.compile(r"\[CHUNK:([^\]]+)\]")
_WORD_RE = re.compile(r"[a-z0-9]+")

# Sentences that are hedges/non-claims don't need a citation.
_NON_CLAIM_MARKERS = (
    "i'm not able", "i am not able", "i cannot", "i can't", "the sources do not",
    "the sources don't", "no information", "isn't covered by the sources",
    "not a doctor", "consult", "speak with", "talk to your",
)
# Min fraction of a claim's content words that must appear in the cited chunk to count
# as entailed (v1 lexical proxy; deliberately lenient, tightened by the LLM judge later).
_ENTAILMENT_THRESHOLD = 0.4

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is",
    "are", "be", "you", "your", "it", "this", "that", "as", "at", "by", "from", "if",
    "can", "may", "will", "do", "does", "not", "no", "so", "than", "then", "which",
}


@dataclass
class SentenceVerdict:
    sentence: str
    is_claim: bool
    cited_ids: list[str]
    valid_citation: bool   # cited id(s) exist in the retrieved set
    entailed: bool         # cited chunk supports the claim
    ok: bool               # overall: non-claim, or claim that is validly cited + entailed


@dataclass
class GroundednessResult:
    verdicts: list[SentenceVerdict]
    cleaned_answer: str    # answer with unsupported claim-sentences removed
    grounded: bool         # True iff no claim-sentence failed

    @property
    def problems(self) -> str:
        bad = [v.sentence for v in self.verdicts if v.is_claim and not v.ok]
        return "; ".join(bad) if bad else ""


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _is_claim(sentence: str) -> bool:
    low = sentence.lower()
    if any(marker in low for marker in _NON_CLAIM_MARKERS):
        return False
    # A sentence with no alphabetic content (e.g. stray punctuation) is not a claim.
    return bool(_WORD_RE.search(low))


def _entails(claim: str, chunk_text: str) -> bool:
    claim_words = _content_words(_CITE_RE.sub("", claim))
    if not claim_words:
        return True
    overlap = claim_words & _content_words(chunk_text)
    return (len(overlap) / len(claim_words)) >= _ENTAILMENT_THRESHOLD


def _split_sentences(answer: str) -> list[str]:
    """Split into sentences, keeping each sentence's trailing [CHUNK:id] citations with it.

    A citation belongs to the sentence it *follows*. So a boundary is sentence punctuation
    (.!?) plus any run of citations/whitespace that immediately trails it; the next
    sentence starts after that. "claim. [CHUNK:x] Next claim. [CHUNK:y]" → two sentences,
    each carrying its own citation.
    """
    # Boundary = .!? then optional spaces + any citation tokens, then before the next word.
    boundary = re.compile(r"(?<=[.!?])(?:\s*\[CHUNK:[^\]]+\])*\s*")
    sentences: list[str] = []
    pos = 0
    for m in boundary.finditer(answer.strip()):
        end = m.end()
        if end <= pos:
            continue
        seg = answer[pos:end].strip()
        if seg:
            sentences.append(seg)
        pos = end
    tail = answer[pos:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def check(answer: str, hits: list[Hit]) -> GroundednessResult:
    by_id = {h.chunk_id: h for h in hits}
    verdicts: list[SentenceVerdict] = []
    kept: list[str] = []

    for sentence in _split_sentences(answer):
        sentence = sentence.strip()
        if not sentence:
            continue
        cited = _CITE_RE.findall(sentence)
        is_claim = _is_claim(sentence)

        if not is_claim:
            verdicts.append(SentenceVerdict(sentence, False, cited, True, True, True))
            kept.append(sentence)
            continue

        valid = bool(cited) and all(cid in by_id for cid in cited)
        entailed = valid and any(_entails(sentence, by_id[cid].text) for cid in cited)
        ok = valid and entailed
        verdicts.append(SentenceVerdict(sentence, True, cited, valid, entailed, ok))
        if ok:
            kept.append(sentence)

    # Grounded iff no factual claim failed. (An answer that is purely a hedge/no-info
    # response — no claims at all — is considered grounded; there is nothing to support.)
    grounded = all(v.ok for v in verdicts if v.is_claim)
    cleaned = " ".join(kept).strip()
    return GroundednessResult(verdicts=verdicts, cleaned_answer=cleaned, grounded=grounded)

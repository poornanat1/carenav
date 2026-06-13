"""Span-level precision / recall / F1 for PII detection. Pure functions, no I/O.

A predicted span MATCHES a gold span when the labels are equal AND the character spans
overlap by at least ``min_overlap`` (fraction of the gold span's length). Overlap-based
matching — not exact-offset — because for redaction what matters is that the PHI token gets
covered; a one-character boundary slip still redacts the value. Recall is the
gate-relevant number: a missed gold span = unredacted PHI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def _span_overlap(a: dict, b: dict) -> int:
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))


def _matches(pred: dict, gold: dict, min_overlap: float) -> bool:
    if pred["label"] != gold["label"]:
        return False
    gold_len = max(1, gold["end"] - gold["start"])
    return _span_overlap(pred, gold) / gold_len >= min_overlap


def score_example(
    pred_spans: list[dict], gold_spans: list[dict], *, min_overlap: float = 0.5
) -> tuple[int, int, int]:
    """Return (tp, fp, fn) for one example. Greedy 1:1 matching, each gold matched once."""
    unmatched_gold = list(gold_spans)
    tp = 0
    fp = 0
    for pred in pred_spans:
        hit = next((g for g in unmatched_gold if _matches(pred, g, min_overlap)), None)
        if hit is not None:
            tp += 1
            unmatched_gold.remove(hit)
        else:
            fp += 1
    fn = len(unmatched_gold)
    return tp, fp, fn


def _prf(tp: int, fp: int, fn: int) -> PRF:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


def aggregate(
    examples: list[tuple[list[dict], list[dict]]], *, min_overlap: float = 0.5
) -> dict[str, PRF]:
    """Score a corpus. Returns per-label PRF plus an ``__overall__`` micro-average.

    ``examples`` is a list of (predicted_spans, gold_spans). Per-label counts let us see
    which entity type the model is weakest on (recall on NAME vs DOB, etc.).
    """
    from collections import defaultdict

    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # label -> [tp, fp, fn]
    for pred_spans, gold_spans in examples:
        labels = {s["label"] for s in pred_spans} | {s["label"] for s in gold_spans}
        for label in labels:
            p = [s for s in pred_spans if s["label"] == label]
            g = [s for s in gold_spans if s["label"] == label]
            tp, fp, fn = score_example(p, g, min_overlap=min_overlap)
            counts[label][0] += tp
            counts[label][1] += fp
            counts[label][2] += fn

    out: dict[str, PRF] = {label: _prf(*c) for label, c in counts.items()}
    micro = [sum(c[i] for c in counts.values()) for i in range(3)]
    out["__overall__"] = _prf(*micro)
    return out

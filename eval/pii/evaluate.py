"""Score PII span predictors on the held-out corpus and print the comparison table.

Predictors share one signature — ``(text: str) -> list[dict]`` (spans) — so the harness
scores them through a single code path:

  * **finetuned** — the fine-tuned SFT model via gateway.classify_pii (needs settings.pii_model)
  * **prompted**  — the SAME prompt against the non-fine-tuned base model (the baseline that
    shows what fine-tuning bought; needs a real generation backend)

Only predictors whose dependencies are available are run, so this works with a fine-tuned
model (both) or with just a key (prompted only).

Output: a per-predictor table of precision/recall/F1 (overall + per entity), with RECALL
called out — a missed gold span is unredacted PHI, the gate-relevant failure.
"""

from __future__ import annotations

import json
import os
from argparse import ArgumentParser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from carenav.config import settings
from carenav.models.gateway import ModelGateway
from eval.pii import metrics


def _load_corpus(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --- predictors ---------------------------------------------------------------------


def _finetuned_predictor(gw: ModelGateway):
    def predict(text: str) -> list[dict]:
        spans = gw.classify_pii(text, model=settings.pii_model)
        return spans or []  # None (unavailable) scored as "found nothing" for the eval
    return predict


def _prompted_predictor(gw: ModelGateway):
    # Same task, base (non-fine-tuned) model — the baseline fine-tuning is measured against.
    def predict(text: str) -> list[dict]:
        spans = gw.classify_pii(text, model=settings.pii_base_model)
        return spans or []
    return predict


def _available_predictors(gw: ModelGateway) -> dict[str, object]:
    preds: dict[str, object] = {}
    if settings.pii_model and gw.using_real_models():
        preds["finetuned"] = _finetuned_predictor(gw)
    if gw.using_real_models():
        preds["prompted"] = _prompted_predictor(gw)
    return preds


# --- runner -------------------------------------------------------------------------


def _score_predictor(
    corpus: list[dict],
    predict: Callable[[str], list[dict]],
    *,
    concurrency: int,
) -> list[tuple[list[dict], list[dict]]]:
    if concurrency <= 1:
        return [(predict(ex["text"]), ex["spans"]) for ex in corpus]

    scored: list[tuple[list[dict], list[dict]] | None] = [None] * len(corpus)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(predict, ex["text"]): i for i, ex in enumerate(corpus)}
        for fut in as_completed(futures):
            i = futures[fut]
            scored[i] = (fut.result(), corpus[i]["spans"])
    return [row for row in scored if row is not None]


def evaluate(
    corpus_path: str | None = None,
    *,
    min_overlap: float = 0.5,
    concurrency: int | None = None,
    limit: int | None = None,
) -> dict:
    corpus_path = corpus_path or os.path.join(settings.pii_corpus_dir, "eval.jsonl")
    if not os.path.isfile(corpus_path):
        raise RuntimeError(
            f"Eval corpus not found at {corpus_path!r}. Generate it: "
            "`python -m carenav.redaction.training.generate_corpus`."
        )
    corpus = _load_corpus(corpus_path)
    if limit is not None:
        corpus = corpus[:limit]
    gw = ModelGateway(capture_prompts=False)
    predictors = _available_predictors(gw)
    if not predictors:
        raise RuntimeError(
            "No predictors available. Need a real generation backend, and optionally a "
            "fine-tuned model route in settings.pii_model (finetuned)."
        )

    concurrency = concurrency or int(os.getenv("PII_EVAL_CONCURRENCY", "8"))
    results: dict[str, dict] = {}
    for name, predict in predictors.items():
        scored = _score_predictor(corpus, predict, concurrency=concurrency)
        results[name] = metrics.aggregate(scored, min_overlap=min_overlap)

    _print_report(results, len(corpus), concurrency=concurrency)
    return results


def _print_report(results: dict[str, dict], n_examples: int, *, concurrency: int) -> None:
    print(
        f"\nPII detector eval — {n_examples} examples, span overlap match, "
        f"concurrency={concurrency}\n"
    )
    header = f"{'predictor':<12} {'P':>6} {'R':>6} {'F1':>6}   per-entity recall"
    print(header)
    print("-" * len(header))
    for name, scores in results.items():
        o = scores["__overall__"]
        per_entity = "  ".join(
            f"{label}={scores[label].recall:.2f}"
            for label in sorted(scores)
            if label != "__overall__"
        )
        print(f"{name:<12} {o.precision:>6.2f} {o.recall:>6.2f} {o.f1:>6.2f}   {per_entity}")
    print()


if __name__ == "__main__":
    parser = ArgumentParser(description="Score the PII span detector on the held-out corpus.")
    parser.add_argument("--corpus", default=None, help="Path to eval JSONL corpus.")
    parser.add_argument("--min-overlap", type=float, default=0.5)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Limit examples for a smoke run.")
    args = parser.parse_args()
    evaluate(
        args.corpus,
        min_overlap=args.min_overlap,
        concurrency=args.concurrency,
        limit=args.limit,
    )

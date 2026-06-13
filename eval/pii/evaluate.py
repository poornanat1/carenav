"""Score PII span predictors on the held-out corpus and print the comparison table.

Predictors share one signature — ``(text: str) -> list[dict]`` (spans) — so the harness
scores them through a single code path:

  * **finetuned** — the fine-tuned SFT model via gateway.classify_pii (needs settings.pii_model)
  * **prompted**  — the SAME prompt against the non-fine-tuned base model (the baseline that
    shows what fine-tuning bought; needs a Mistral key but no fine-tuned model)

Only predictors whose dependencies are available are run, so this works with a fine-tuned
model (both) or with just a key (prompted only). Both need a Mistral key.

Output: a per-predictor table of precision/recall/F1 (overall + per entity), with RECALL
called out — a missed gold span is unredacted PHI, the gate-relevant failure.
"""

from __future__ import annotations

import json
import os

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


def evaluate(corpus_path: str | None = None, *, min_overlap: float = 0.5) -> dict:
    corpus_path = corpus_path or os.path.join(settings.pii_corpus_dir, "eval.jsonl")
    if not os.path.isfile(corpus_path):
        raise RuntimeError(
            f"Eval corpus not found at {corpus_path!r}. Generate it: "
            "`python -m carenav.redaction.training.generate_corpus`."
        )
    corpus = _load_corpus(corpus_path)
    gw = ModelGateway(capture_prompts=False)
    predictors = _available_predictors(gw)
    if not predictors:
        raise RuntimeError(
            "No predictors available. Need a Mistral key (prompted), and optionally a "
            "fine-tuned model id in settings.pii_model (finetuned)."
        )

    results: dict[str, dict] = {}
    for name, predict in predictors.items():
        scored = [(predict(ex["text"]), ex["spans"]) for ex in corpus]
        results[name] = metrics.aggregate(scored, min_overlap=min_overlap)

    _print_report(results, len(corpus))
    return results


def _print_report(results: dict[str, dict], n_examples: int) -> None:
    print(f"\nPII detector eval — {n_examples} examples, span overlap match\n")
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
    evaluate()

"""Unit tests for the PII span metrics — pure, offline."""

from eval.pii import metrics


def _span(start, end, label):
    return {"start": start, "end": end, "label": label}


def test_exact_match_is_true_positive():
    tp, fp, fn = metrics.score_example([_span(0, 5, "NAME")], [_span(0, 5, "NAME")])
    assert (tp, fp, fn) == (1, 0, 0)


def test_label_mismatch_is_not_a_match():
    # Same offsets, wrong label → false positive + false negative, not a match.
    tp, fp, fn = metrics.score_example([_span(0, 5, "DOB")], [_span(0, 5, "NAME")])
    assert (tp, fp, fn) == (0, 1, 1)


def test_partial_overlap_above_threshold_matches():
    # Predict 0..4 against gold 0..6 → 4/6 = 0.67 overlap ≥ 0.5 default → match.
    tp, fp, fn = metrics.score_example([_span(0, 4, "NAME")], [_span(0, 6, "NAME")])
    assert (tp, fp, fn) == (1, 0, 0)


def test_tiny_overlap_below_threshold_does_not_match():
    # Predict 0..2 against gold 0..10 → 2/10 = 0.2 < 0.5 → miss (fp + fn).
    tp, fp, fn = metrics.score_example([_span(0, 2, "NAME")], [_span(0, 10, "NAME")])
    assert (tp, fp, fn) == (0, 1, 1)


def test_missed_gold_span_is_false_negative():
    # The gate-relevant failure: gold PHI with no prediction = unredacted PHI.
    tp, fp, fn = metrics.score_example([], [_span(0, 5, "NAME")])
    assert (tp, fp, fn) == (0, 0, 1)


def test_each_gold_matched_once():
    # Two predictions over one gold span → one TP, one FP (gold consumed).
    tp, fp, fn = metrics.score_example(
        [_span(0, 5, "NAME"), _span(0, 5, "NAME")], [_span(0, 5, "NAME")]
    )
    assert (tp, fp, fn) == (1, 1, 0)


def test_aggregate_per_label_and_overall():
    examples = [
        ([_span(0, 5, "NAME")], [_span(0, 5, "NAME")]),          # NAME tp
        ([], [_span(0, 8, "DOB")]),                              # DOB fn (missed)
        ([_span(0, 4, "ADDRESS")], []),                          # ADDRESS fp (spurious)
    ]
    out = metrics.aggregate(examples)
    assert out["NAME"].recall == 1.0
    assert out["DOB"].recall == 0.0  # a miss tanks recall — the PHI leaked
    assert out["ADDRESS"].precision == 0.0
    overall = out["__overall__"]
    assert (overall.tp, overall.fp, overall.fn) == (1, 1, 1)

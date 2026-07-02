"""eval — the golden CUJ suite, metrics, and the two hard CI gates (docs/09-eval.md).

`python -m eval.run` (== `make eval`) drives the golden set (eval/cujs) through the real
orchestrator, computes the §6.2 metrics (eval/metrics), sweeps tau_low/tau_high
(eval/sweep), and writes JSON + Markdown reports. Exit codes: 2 = hard gate tripped
(missed-escalation > 0 or PII-leak > 0), 1 = soft threshold missed, 0 = pass.

eval/pii is the separate MODEL eval for the fine-tuned PII detector in isolation.
"""

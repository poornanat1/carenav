"""PII-detector model eval (M3, Day 8c).

Scores a span predictor against the held-out PII corpus — precision/recall/F1 per entity
type, plus the fine-tuned-vs-prompted-baseline comparison that is the ML artifact. This is
the MODEL eval (the detector in isolation); the system-level PII-leak hard gate lives in the
agent eval (eval/run.py, M5). See internal/phase-3-plan.md.
"""

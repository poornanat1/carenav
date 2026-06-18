# 15 — Non-Goals, Risks & Posture

Implements spec §12. Read this alongside [00-overview.md](00-overview.md) (scope) and
[09-eval.md](09-eval.md) (the gates that enforce it).

## Non-goals (hard boundaries)

- **Not a diagnostic or medical-advice tool.** It navigates benefits and surfaces
  vetted info. Clinical judgment escalates to humans. State this in the UI and README.
- **No diagnosis, no treatment decisions, no dosing advice.** These are declined and
  redirected (CUJ-7).

## Risks & posture

| Risk | Posture |
|---|---|
| **Real PHI** | All patient/member PHI is synthetic (Synthea). Never wire real PHI into the build. Provider data (NPPES) is real but public and carries no patient PHI. Synthea + NPPES are the entire data story. |
| **Gaming containment** | The safety gate is non-negotiable. Missed-escalation rate = 0 blocks merges. Don't raise containment by suppressing escalations. ([09](09-eval.md)) |
| **Prompt injection** | KB docs are untrusted content. The orchestrator treats retrieved text as data, never as instructions (tested by CUJ-10). ([07](07-rag.md)) |
| **PHI leakage to a model** | Redaction layer plus hard gate. PII-leakage rate = 0. ([05](05-redaction.md)) |

## The two principles that override everything

1. **Missed-escalation rate = 0** — safety over containment, always.
2. **PII-leakage rate = 0** — no raw PHI to any model, ever.

Both are hard CI gates ([09-eval.md](09-eval.md)). A regression in either blocks merge
regardless of the other numbers. They are not tunable.

## Tone for the README / UI

- Lead with what it does (benefits navigation) and what it won't do (clinical judgment).
- Be explicit that escalation is a safety feature, not a fallback failure.

# 13 — Build Plan

Implements spec §11. **Each milestone is independently demoable.**

| M | Deliverable | Demo | Doc |
|---|---|---|---|
| **M0** | Data pipeline | `make data` → populated Postgres + vector store w/ asserted row counts | [08](08-data-model.md) |
| **M1** | Single RAG agent + grounding | Ask a medication question, get a cited, grounded answer | [07](07-rag.md) |
| **M2** | Orchestrator + all specialist tools | Multi-tool turn: "did I meet my deductible and is an MRI covered?" | [03](03-orchestrator.md), [04](04-agents.md) |
| **M3** | PII/PHI redaction layer | Show captured model input — fully tokenized; audit log clean | [05](05-redaction.md) |
| **M4** | Tiered models + escalation | Threshold sweep chart: small-model coverage vs quality vs cost | [06](06-model-tiering.md) |
| **M5** | Eval harness + CI gates | `make eval` → report; emergent-symptom + PII gates enforced | [09](09-eval.md) |
| **M6** | Scalability doc + deployment mapping | README scale story; `deployment-mapping.md` | [12](12-scalability.md), [14](14-deployment-mapping.md) |

## Sequencing guidance

- **Ship M1–M3 first** if you need a fast credible demo.
- **M4–M6** are where the "production" signal compounds (cost optimization, eval
  discipline, value articulation, scale story).

## Dependency notes

- **M0 is the foundation** — nothing else runs without the dataset.
- **M1** needs only the KB corpus + vector store (M0 step 4) and a single RAG agent —
  it does not require the full orchestrator.
- **M2** assembles the full orchestrator (a typed node pipeline) and all specialist tools
  on top of the M0 structured data.
- **M3** (redaction) wraps the M2 tool/model boundary. It can be scaffolded earlier but
  is only meaningfully demoable once tools feed real member records into context.
- **M4** depends on the `ModelGateway` cost capture, which should be built into the
  gateway from M1 onward so cost numbers accrue across milestones.
- **M5** consumes everything: it asserts the hard gates against the running system.
- **M6** is presentation/packaging — it reads the measured numbers from M4/M5 telemetry
  and eval output.

## What "done" looks like

`docker compose up` runs the stack; `make data`, `make eval`, `make run` all work; the
React frontend shows the chat view with a live gate-status banner; CI enforces the two
hard gates.

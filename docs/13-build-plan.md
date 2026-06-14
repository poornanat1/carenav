# 13 — Build Plan

Implements spec §11. **Each delivery stage is independently demoable.**

| Stage | Deliverable | Demo | Doc |
|---|---|---|---|
| Data foundation | Data pipeline | `make data` → populated Postgres + vector store w/ asserted row counts | [08](08-data-model.md) |
| RAG foundation | Single RAG agent + grounding | Ask a medication question, get a cited, grounded answer | [07](07-rag.md) |
| Orchestrator | Orchestrator + all specialist tools | Multi-tool turn: "did I meet my deductible and is an MRI covered?" | [03](03-orchestrator.md), [04](04-agents.md) |
| Redaction | PII/PHI redaction layer | Show captured model input — fully tokenized; audit log clean | [05](05-redaction.md) |
| Tiering | Tiered models + escalation | Threshold sweep chart: small-model coverage vs quality vs cost | [06](06-model-tiering.md) |
| Evaluation | Eval harness + CI gates | `make eval` → report; emergent-symptom + PII gates enforced | [09](09-eval.md) |
| Deployment story | Scalability doc + deployment mapping | README scale story; `deployment-mapping.md` | [12](12-scalability.md), [14](14-deployment-mapping.md) |

## Sequencing guidance

- **Ship the data, RAG, orchestrator, and redaction stages first** if you need a fast credible demo.
- **Tiering, evaluation, and deployment docs** are where the "production" signal compounds (cost optimization, eval
  discipline, value articulation, scale story).

## Dependency notes

- **Data is the foundation** — nothing else runs without the dataset.
- **RAG** needs only the KB corpus + vector store and a single RAG agent —
  it does not require the full orchestrator.
- **The orchestrator** assembles the typed node pipeline and all specialist tools
  on top of the structured data.
- **Redaction** wraps the tool/model boundary. It can be scaffolded earlier but
  is only meaningfully demoable once tools feed real member records into context.
- **Tiering** depends on the `ModelGateway` cost capture, which should be built into the
  gateway from the RAG foundation onward so cost numbers accrue across stages.
- **Evaluation** consumes everything: it asserts the hard gates against the running system.
- **Deployment packaging** reads the measured numbers from tiering/eval telemetry
  and eval output.

## What "done" looks like

`docker compose up` runs the stack; `make data`, `make eval`, `make run` all work; the
React frontend shows the chat view with a live gate-status banner; CI enforces the two
hard gates.

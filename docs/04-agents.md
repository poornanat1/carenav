# 04 — Specialist Agents (Tools)

Implements spec §4.2. Lives in `carenav/agents/`.

Each agent is a **typed function with a Pydantic input/output contract** and declares
which data source backs it.

## Agent catalogue

| Agent | Input | Output | Backed by |
|---|---|---|---|
| **Member/Account** | `member_ref` | `plan_id`, `eligibility_status`, coverage dates, accumulators (`deductible_met`, `oop_met`) | Synthea-derived member + accumulator tables |
| **Coverage/Benefit** | `service_code` or category, `plan_id` | `covered?`, `copay`, `coinsurance`, `prior_auth_required`, `notes` | Benefit-rule table + SBC RAG |
| **Claims** | `member_ref`, `claim_id?` | claim status, billed/allowed/paid, member responsibility, `denial_reason` | Synthea claims |
| **Provider search** | `specialty`, `location`, `accepting_new?` | ranked in-network providers (name, address, distance) | NPPES + plan network table |
| **KB/RAG** | `query` | top-k chunks w/ source + score | Vector store (MedlinePlus/CDC + openFDA labels + SBC docs) — see [07](07-rag.md) |
| **Triage classifier** | raw turn text | `none \| urgent \| emergent` + matched signals | Rules + small classifier |

## Design rules (non-negotiable)

1. **Structured data, not prose.** Agents return typed Pydantic objects. The
   orchestrator owns all natural-language generation.
2. **Agents never call a model directly.** (The triage classifier may use a small
   classifier model, but it is invoked via the orchestrator's `safety_triage` node,
   not as a generative call.)
3. **Every agent result passes through redaction** before re-entering graph state.
   An agent that reads a member record introduces PHI into context; that PHI must be
   tokenized at the `tool_exec` boundary.

## Contract pattern

```python
class AgentInput(BaseModel):
    ...  # typed, validated

class AgentOutput(BaseModel):
    ...  # typed, validated; carries source refs where applicable

def member_account(inp: MemberAccountInput) -> MemberAccountOutput:
    ...
```

Each agent should also surface a **completeness signal** — did the lookup return all
required fields? This feeds `tool_conf` in the confidence breakdown
([06-model-tiering.md](06-model-tiering.md)).

## member_ref indirection

The orchestrator passes `member_ref` (an opaque session reference), **not** the real
`member_id`. The agent layer resolves `member_ref → member_id` internally, against the
session store, so the real identifier never travels through graph state or prompts.

## Implementation status

**M2 agents shipped** (`carenav/agents/`): Member/Account, Coverage/Benefit, Claims, and
Provider-search — each a typed Pydantic in/out contract over Postgres, returning structured
data and **never calling a model**. Every output carries a completeness signal
(`complete`/`missing`) feeding `tool_conf` (docs/06). `member_ref → member_id` resolution
lives in `agents/session.py`. The orchestrator's `plan → tool_exec → reflect` loop
(`orchestrator/tools.py`) runs the tools a turn needs and wraps their structured facts as
groundable sources, so benefit/claim/account facts are cited (`[CHUNK:tool:<name>]`) and
grounded by the same contract as KB chunks. The Triage classifier lives in the orchestrator's
`route` node (`orchestrator/router.py`).

## Triage classifier — special status

The triage classifier is the **safety-critical** agent. Its `emergent` output forces
an immediate `escalate_human` jump in the orchestrator and a Tier 3 routing override
([06](06-model-tiering.md)). It runs on the **raw** turn before redaction so emergent
signals are never masked by tokenization. Its recall on emergent cases is gated to
**100%** in eval ([09-eval.md](09-eval.md)) — missed-escalation rate must be 0.

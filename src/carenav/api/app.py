"""FastAPI async turn endpoint (docs/03 node 11 / docs/01) — serves the orchestrator.

POST /turn runs one member turn through run_turn and returns the structured result
(answer + citations, or an escalation handoff). The orchestrator is sync + DB/LLM-bound,
so it runs in a threadpool to keep the event loop free.

This is the serving surface used by the React frontend.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from carenav.orchestrator import run_turn

app = FastAPI(title="CareNav", version="0.1.0")


class TurnRequest(BaseModel):
    question: str = Field(min_length=1)
    member_ref: str | None = None


class CitationOut(BaseModel):
    chunk_id: str
    title: str
    source_url: str | None = None


class HandoffOut(BaseModel):
    reason: str
    suspected_intent: str | None
    safety_flag: str
    gathered: list[str]


class TurnResponse(BaseModel):
    answer: str
    intent: str | None
    grounded: bool
    escalated: bool
    citations: list[CitationOut]
    handoff: HandoffOut | None
    tier_used: str
    safety_flag: str
    confidence: float
    cost_usd: float


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/turn", response_model=TurnResponse)
async def turn(req: TurnRequest) -> TurnResponse:
    result = await run_in_threadpool(run_turn, req.question, req.member_ref)
    return TurnResponse(
        answer=result.answer,
        intent=result.intent,
        grounded=result.grounded,
        escalated=result.escalated,
        citations=[
            CitationOut(chunk_id=c.chunk_id, title=c.title, source_url=c.source_url or None)
            for c in result.citations
        ],
        handoff=(
            HandoffOut(
                reason=result.handoff.reason,
                suspected_intent=result.handoff.suspected_intent,
                safety_flag=result.handoff.safety_flag,
                gathered=result.handoff.gathered,
            )
            if result.handoff
            else None
        ),
        tier_used=result.tier_used,
        safety_flag=result.safety_flag,
        confidence=result.confidence.weighted_sum(),
        cost_usd=result.cost_usd,
    )

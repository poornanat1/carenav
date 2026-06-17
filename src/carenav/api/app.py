"""FastAPI serving surface for CareNav."""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from carenav.agents import create_demo_member_ref
from carenav.config import settings
from carenav.api.members import list_member_summaries, suggested_questions_for_member
from carenav.api.profile_turn import profile_turn
from carenav.api.schemas import (
    CitationOut,
    HandoffOut,
    MemberSummary,
    SuggestedQuestion,
    TurnRequest,
    TurnResponse,
)
from carenav.models import ModelGateway
from carenav.orchestrator import run_turn
from carenav.orchestrator.state import TurnResult

app = FastAPI(title="CareNav", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/members", response_model=list[MemberSummary])
async def members() -> list[MemberSummary]:
    return await run_in_threadpool(list_member_summaries)


@app.get("/members/{member_id}/suggested-questions", response_model=list[SuggestedQuestion])
async def suggested_questions(member_id: str) -> list[SuggestedQuestion]:
    return await run_in_threadpool(suggested_questions_for_member, member_id)


def _member_ref(req: TurnRequest) -> str | None:
    return req.member_ref or (create_demo_member_ref(req.member_id) if req.member_id else None)


def _excerpt(text: str, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _citation_excerpts(result: TurnResult) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for answer in result.rag_answers:
        for hit in answer.hits:
            if hit.chunk_id not in excerpts:
                excerpts[hit.chunk_id] = _excerpt(hit.text)
    return excerpts


def _serialize_turn(result: TurnResult) -> TurnResponse:
    excerpts = _citation_excerpts(result)
    return TurnResponse(
        answer=result.answer,
        intent=result.intent,
        grounded=result.grounded,
        escalated=result.escalated,
        citations=[
            CitationOut(
                chunk_id=c.chunk_id,
                title=c.title,
                source_url=c.source_url or None,
                excerpt=excerpts.get(c.chunk_id),
            )
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


@app.post("/turn", response_model=TurnResponse)
async def turn(req: TurnRequest) -> TurnResponse:
    gateway = ModelGateway()
    profile_result = (
        await run_in_threadpool(
            profile_turn, req.question, req.member_ref, req.member_id, gateway
        )
        if req.member_ref or req.member_id
        else None
    )
    result = profile_result or await run_in_threadpool(
        run_turn, req.question, _member_ref(req), gateway
    )
    return _serialize_turn(result)

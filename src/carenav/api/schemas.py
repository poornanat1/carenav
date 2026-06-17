"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TurnRequest(BaseModel):
    question: str = Field(min_length=1)
    member_ref: str | None = None
    member_id: str | None = None


class CitationOut(BaseModel):
    chunk_id: str
    title: str
    source_url: str | None = None
    excerpt: str | None = None


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


class MemberSummary(BaseModel):
    id: str
    name: str
    age: int
    plan: str
    summary: str
    member_ref: str
    plan_type: str
    deductible: dict[str, float]
    oop: dict[str, float]
    medications: list[str]
    conditions: list[str]
    kb_topics: list[str]
    recent_claims: list[dict]
    recent_providers: list[dict]
    note: str


class SuggestedQuestion(BaseModel):
    label: str
    question: str
    intent: str

"""SQLAlchemy ORM models — the structured tier.

Mirrors docs/08-data-model.md. PHI fields are marked in comments; the redaction layer
(carenav/redaction) keys on exactly these. Nothing here decides redaction — these
are storage definitions only.

KBDoc/Chunk live in carenav/rag so the vector column lives next to retrieval code.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = "plan"

    plan_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    deductible: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    oop_max: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    coinsurance: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    # copays_by_category kept on the benefit-rule table; plan holds plan-level numbers.

    members: Mapped[list[Member]] = relationship(back_populates="plan")
    benefit_rules: Mapped[list[BenefitRule]] = relationship(back_populates="plan")


class Member(Base):
    __tablename__ = "member"

    member_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)          # PHI
    dob: Mapped[date] = mapped_column(Date, nullable=False)             # PHI
    address: Mapped[str] = mapped_column(String, nullable=False)        # PHI
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan.plan_id"), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    coverage_start: Mapped[date] = mapped_column(Date, nullable=False)
    coverage_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="members")
    claims: Mapped[list[Claim]] = relationship(back_populates="member")
    accumulators: Mapped[list[Accumulator]] = relationship(back_populates="member")
    conditions: Mapped[list[Condition]] = relationship(back_populates="member")


class Accumulator(Base):
    __tablename__ = "accumulator"
    __table_args__ = (UniqueConstraint("member_id", "plan_year", name="uq_acc_member_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("member.member_id"), nullable=False)
    plan_year: Mapped[int] = mapped_column(Integer, nullable=False)
    deductible_met: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    oop_met: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    member: Mapped[Member] = relationship(back_populates="accumulators")


class Claim(Base):
    __tablename__ = "claim"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("member.member_id"), nullable=False)
    provider_npi: Mapped[str | None] = mapped_column(String, nullable=True)
    service_code: Mapped[str] = mapped_column(String, nullable=False)
    billed: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    allowed: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    member_responsibility: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # paid|denied|pending
    status: Mapped[str] = mapped_column(String, nullable=False, default="paid")
    denial_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    member: Mapped[Member] = relationship(back_populates="claims")


class Condition(Base):
    """A member's diagnosed condition (FHIR Condition-shaped, ICD-10 coded).

    Links a member to a chronic/active diagnosis so a turn can reason over what the patient
    actually has (e.g. "I have diabetes — is my metformin covered?"). The `kb_topic` ties
    the diagnosis to the KB corpus (a consumer_health or drug_label doc_id stem) so the RAG
    layer and the structured data line up. Diagnoses are synthetic, never real PHI.
    """

    __tablename__ = "condition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("member.member_id"), nullable=False)
    icd10: Mapped[str] = mapped_column(String, nullable=False)
    display: Mapped[str] = mapped_column(String, nullable=False)
    clinical_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    onset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # KB topic key (e.g. "type-2-diabetes") linking this diagnosis to the corpus.
    kb_topic: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (UniqueConstraint("member_id", "icd10", name="uq_condition_member_icd"),)

    member: Mapped[Member] = relationship(back_populates="conditions")


class BenefitRule(Base):
    __tablename__ = "benefit_rule"
    __table_args__ = (
        UniqueConstraint("plan_id", "key", name="uq_benefit_plan_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan.plan_id"), nullable=False)
    # `key` is a service_code OR a category (e.g. "MRI", "specialist_visit").
    key: Mapped[str] = mapped_column(String, nullable=False)
    is_category: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    covered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    copay: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    coinsurance: Mapped[float | None] = mapped_column(Float, nullable=True)
    prior_auth_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="benefit_rules")


class Provider(Base):
    __tablename__ = "provider"

    npi: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    taxonomy: Mapped[str | None] = mapped_column(String, nullable=True)
    specialty: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    accepting_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    networks: Mapped[list[PlanNetwork]] = relationship(back_populates="provider")


class PlanNetwork(Base):
    """Synthetic join marking which providers are in-network for a plan."""

    __tablename__ = "plan_network"
    __table_args__ = (UniqueConstraint("plan_id", "npi", name="uq_network_plan_npi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plan.plan_id"), nullable=False)
    npi: Mapped[str] = mapped_column(ForeignKey("provider.npi"), nullable=False)
    in_network: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    provider: Mapped[Provider] = relationship(back_populates="networks")

"""Policies, recomputations and findings (Phase 5). Money is NUMERIC(14,2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from compback_core.models.base import Base, IdMixin, TimestampMixin

MONEY = Numeric(14, 2)


class Policy(IdMixin, TimestampMixin, Base):
    __tablename__ = "policies"
    __table_args__ = (Index("ix_policies_org", "org_id", "period_start"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    carrier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    policy_number: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str] = mapped_column(
        String(2), ForeignKey("jurisdiction_policies.code"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class Recomputation(IdMixin, Base):
    __tablename__ = "recomputations"
    __table_args__ = (Index("ix_recomputations_policy", "policy_id", "created_at"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(20), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_extraction_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    billed_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    recomputed_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    estimate_low: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    estimate_high: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Finding(IdMixin, Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint(
            "reviewer_status IN ('pending','confirmed','rejected','needs_expert')",
            name="reviewer_status",
        ),
        CheckConstraint("impact_low <= impact_high", name="impact_range"),
        Index("ix_findings_recomputation", "recomputation_id"),
        Index("ix_findings_org_status", "org_id", "reviewer_status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    recomputation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recomputations.id", ondelete="CASCADE"), nullable=False
    )
    detector: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_status: Mapped[str] = mapped_column(String(12), nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    impact_low: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    impact_high: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default="0")
    customer_visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reviewer_status: Mapped[str] = mapped_column(
        String(15), nullable=False, server_default="pending"
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""Cases, dispute packages, outcomes, fees, and Stripe event idempotency (Phases 7-8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from compback_core.models.base import Base, IdMixin, TimestampMixin

MONEY = Numeric(14, 2)
CASE_STATUSES = (
    "draft",
    "ready_for_review",
    "approved_by_customer",
    "submitted",
    "carrier_responded",
    "resolved",
    "fee_invoiced",
    "closed",
    "withdrawn",
)


class Case(IdMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','ready_for_review','approved_by_customer','submitted',"
            "'carrier_responded','resolved','fee_invoiced','closed','withdrawn')",
            name="status",
        ),
        CheckConstraint(
            "deadline_date IS NULL OR deadline_source IS NOT NULL", name="deadline_needs_source"
        ),
        Index("ix_cases_org_status", "org_id", "status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    recomputation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recomputations.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(25), nullable=False, server_default="draft")
    submitter_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    deadline_date: Mapped[date | None] = mapped_column(Date)
    deadline_source: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    submission_method: Mapped[str | None] = mapped_column(String(40))
    resolution: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class CaseEvent(IdMixin, Base):
    """Transitions and carrier-contact log entries for a case (also mirrored in audit_log)."""

    __tablename__ = "case_events"
    __table_args__ = (Index("ix_case_events_case", "case_id", "created_at"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(25))
    to_status: Mapped[str | None] = mapped_column(String(25))
    note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DisputePackage(IdMixin, Base):
    __tablename__ = "dispute_packages"
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_dispute_packages_case_ver"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    total_low: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_high: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pdf_key: Mapped[str] = mapped_column(String(300), nullable=False)
    docx_key: Mapped[str] = mapped_column(String(300), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Outcome(IdMixin, Base):
    __tablename__ = "outcomes"
    __table_args__ = (
        CheckConstraint("kind IN ('refund','credit','denied','partial')", name="kind"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        Index("ix_outcomes_case", "case_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    received_on: Mapped[date | None] = mapped_column(Date)
    proof_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Fee(IdMixin, TimestampMixin, Base):
    __tablename__ = "fees"
    __table_args__ = (
        CheckConstraint("kind IN ('analysis','contingency')", name="kind"),
        CheckConstraint(
            "status IN ('draft','invoiced','paid','void','refunded','disputed')", name="status"
        ),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        Index("ix_fees_org", "org_id", "status"),
        Index(
            "uq_fees_case_kind", "case_id", "kind", unique=True, postgresql_where="status <> 'void'"
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    basis_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    credit_applied: Mapped[Decimal] = mapped_column(MONEY, nullable=False, server_default="0")
    cap: Mapped[Decimal | None] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text)


class StripeEvent(Base):
    """Webhook idempotency: one row per Stripe event id; duplicates are ignored."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""Platform-wide tables: jurisdiction policy (ADR-0009) and the job queue (ADR-0003)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from compback_core.models.base import Base, IdMixin, TimestampMixin

SUBMITTER_MODES = ("customer_only", "customer_or_own_advisor", "licensed_partner")
JOB_STATES = ("queued", "running", "succeeded", "failed", "parked")


class JurisdictionPolicy(TimestampMixin, Base):
    """Per-state operating policy. Global (not tenant data); app role has read-only access."""

    __tablename__ = "jurisdiction_policies"
    __table_args__ = (
        CheckConstraint(
            "submitter_mode IN ('customer_only','customer_or_own_advisor','licensed_partner')",
            name="submitter_mode",
        ),
        CheckConstraint(
            "NOT (monopolistic AND (free_scan_allowed OR paid_analysis_allowed))",
            name="monopolistic_declined",
        ),
    )

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    monopolistic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    free_scan_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    paid_analysis_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    contingency_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    submitter_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="customer_only"
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    citations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    reviewed_by_counsel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(IdMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','running','succeeded','failed','parked')", name="state"
        ),
        Index("ix_jobs_claim", "state", "run_after"),
        Index("ix_jobs_org", "org_id", "state"),
        Index(
            "uq_jobs_idempotency",
            "org_id",
            "kind",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    state: Mapped[str] = mapped_column(String(10), nullable=False, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

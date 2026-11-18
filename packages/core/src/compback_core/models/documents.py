"""Document vault models (Phase 3). Content is never stored in the database unencrypted."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from compback_core.models.base import Base, IdMixin

DOC_STATUSES = ("uploaded", "processing", "ready", "rejected", "deleted")
DOC_TYPES = (
    "unknown",
    "policy_declarations",
    "premium_audit",
    "audit_billing",
    "experience_rating",
    "payroll_register",
    "payroll_tax_form",
    "certificate_of_insurance",
    "carrier_correspondence",
    "quote",
)


class Document(IdMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','processing','ready','rejected','deleted')", name="status"
        ),
        CheckConstraint(
            "malware_status IN ('pending','clean','infected','error')", name="malware_status"
        ),
        Index("ix_documents_org_created", "org_id", "created_at"),
        Index("ix_documents_retention", "retention_until"),
        Index(
            "uq_documents_org_sha",
            "org_id",
            "sha256",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="unknown")
    file_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(300))
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="uploaded")
    malware_status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="pending"
    )
    redaction_count: Mapped[int | None] = mapped_column(Integer)
    rejection_code: Mapped[str | None] = mapped_column(String(40))
    rejection_message: Mapped[str | None] = mapped_column(Text)
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    upload_source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="web")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentPage(IdMixin, Base):
    """Redacted derivatives. ``text_enc`` and the stored image are envelope-encrypted."""

    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_no", name="uq_document_pages_doc_page"),
        Index("ix_document_pages_org", "org_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text_source: Mapped[str] = mapped_column(String(10), nullable=False)
    text_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    redactions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    image_key: Mapped[str | None] = mapped_column(String(300))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)


class Extraction(IdMixin, Base):
    """Structured data extracted from one document. Feeds the engine only once verified/ready."""

    __tablename__ = "extractions"
    __table_args__ = (
        CheckConstraint("status IN ('needs_review','ready','verified','failed')", name="status"),
        Index("ix_extractions_doc", "document_id", "created_at"),
        Index("ix_extractions_org", "org_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    extractor: Mapped[str] = mapped_column(String(60), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    review_reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    min_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    llm_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    llm_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    llm_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExtractionEdit(IdMixin, Base):
    """Human corrections. Kept as evaluation data (used only with consent; see ADR)."""

    __tablename__ = "extraction_edits"
    __table_args__ = (Index("ix_extraction_edits_ext", "extraction_id"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extractions.id", ondelete="CASCADE"), nullable=False
    )
    field_path: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""Human verification of extracted data (side-by-side with the redacted page images)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from compback_api.deps import CurrentOrg, OrgAccess, OrgDb
from compback_core import audit
from compback_core.models import Document, Extraction, ExtractionEdit
from compback_extract.pipeline import apply_edits, mark_verified

router = APIRouter(prefix="/orgs/{org_id}/documents/{doc_id}/extraction", tags=["extraction"])


class ExtractionOut(BaseModel):
    id: str
    doc_type: str
    schema_name: str
    schema_version: str
    extractor: str
    status: str
    review_reasons: list[str]
    min_confidence: Decimal | None
    issues: list[dict[str, Any]]
    data: dict[str, Any]
    created_at: datetime
    verified_at: datetime | None


class EditIn(BaseModel):
    path: str = Field(min_length=1, max_length=120, pattern=r"^[a-z_]+(\[\d+\])?(\.[a-z_]+)?$")
    value: str | None = Field(default=None, max_length=200)


class EditsIn(BaseModel):
    edits: list[EditIn] = Field(min_length=1, max_length=100)


def _latest(db: OrgDb, access: OrgAccess, doc_id: uuid.UUID) -> Extraction:
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == access.org_id))
    if doc is None or doc.status == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    row = db.scalar(
        select(Extraction)
        .where(Extraction.document_id == doc_id)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no extraction yet")
    return row


def _out(row: Extraction) -> ExtractionOut:
    return ExtractionOut(
        id=str(row.id),
        doc_type=row.doc_type,
        schema_name=row.schema_name,
        schema_version=row.schema_version,
        extractor=row.extractor,
        status=row.status,
        review_reasons=row.review_reasons,
        min_confidence=row.min_confidence,
        issues=row.issues,
        data=row.data,
        created_at=row.created_at,
        verified_at=row.verified_at,
    )


@router.get("")
def get_extraction(doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> ExtractionOut:
    return _out(_latest(db, access, doc_id))


@router.patch("")
def edit_extraction(
    doc_id: uuid.UUID, body: EditsIn, access: CurrentOrg, db: OrgDb
) -> ExtractionOut:
    row = _latest(db, access, doc_id)
    if row.status == "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "already verified; re-open first")
    try:
        applied = apply_edits(row, [(e.path, e.value) for e in body.edits])
    except (KeyError, IndexError, ValueError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid edit") from exc
    for path, old, new in applied:
        db.add(
            ExtractionEdit(
                org_id=access.org_id,
                extraction_id=row.id,
                field_path=path,
                old_value=old,
                new_value=new,
                edited_by=access.principal.user_id,
            )
        )
    row.status = "needs_review"
    audit.record(
        db,
        action="extraction.edited",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="extraction",
        target_id=row.id,
        details={"fields": [p for p, _, _ in applied]},
    )
    return _out(row)


@router.post("/verify")
def verify_extraction(doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> ExtractionOut:
    row = _latest(db, access, doc_id)
    mark_verified(row, access.principal.user_id)
    audit.record(
        db,
        action="extraction.verified",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="extraction",
        target_id=row.id,
        details={"open_issues": len(row.issues)},
    )
    return _out(row)

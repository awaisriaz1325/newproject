"""Public, read-only jurisdiction policy (ADR-0009)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from compback_core.db import tenant_session
from compback_core.models import JurisdictionPolicy

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


class JurisdictionOut(BaseModel):
    code: str
    name: str
    monopolistic: bool
    free_scan_allowed: bool
    paid_analysis_allowed: bool
    contingency_allowed: bool
    submitter_mode: str
    notes: str
    citations: list[str]


@router.get("")
def list_jurisdictions() -> list[JurisdictionOut]:
    with tenant_session(None) as db:
        rows = db.scalars(select(JurisdictionPolicy).order_by(JurisdictionPolicy.code))
        return [
            JurisdictionOut(
                code=r.code,
                name=r.name,
                monopolistic=r.monopolistic,
                free_scan_allowed=r.free_scan_allowed,
                paid_analysis_allowed=r.paid_analysis_allowed,
                contingency_allowed=r.contingency_allowed,
                submitter_mode=r.submitter_mode,
                notes=r.notes,
                citations=r.citations,
            )
            for r in rows
        ]

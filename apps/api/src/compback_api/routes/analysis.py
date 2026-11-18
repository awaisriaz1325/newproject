"""Policies, analysis runs (recompute + detectors) and the reviewer workflow on findings."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from compback_api.deps import CurrentOrg, OrgAccess, OrgDb, utcnow
from compback_core import audit
from compback_core.models import (
    Document,
    Extraction,
    Finding,
    JurisdictionPolicy,
    Policy,
    Recomputation,
)
from compback_ml.prioritize import priority_score
from compback_rating.adapters import build_context
from compback_rating.analysis import analyze

router = APIRouter(prefix="/orgs/{org_id}/policies", tags=["analysis"])
USABLE = ("ready", "verified")


class PolicyIn(BaseModel):
    carrier_name: str = Field(min_length=2, max_length=200)
    policy_number: str = Field(min_length=2, max_length=60)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    period_start: date
    period_end: date


class PolicyOut(BaseModel):
    id: str
    carrier_name: str
    policy_number: str
    state: str
    period_start: date
    period_end: date
    document_ids: list[str]


class FindingOut(BaseModel):
    id: str
    detector: str
    rule_id: str
    rule_status: str
    citations: list[dict[str, Any]]
    title: str
    explanation: str
    conditions: list[str]
    evidence: list[dict[str, Any]]
    impact_low: Decimal
    impact_high: Decimal
    confidence: Decimal
    priority_score: Decimal
    customer_visible: bool
    reviewer_status: str
    reviewer_note: str | None


class AnalysisOut(BaseModel):
    recomputation_id: str
    created_at: datetime
    engine_version: str
    registry_version: str
    billed_total: Decimal
    recomputed_total: Decimal
    estimate_low: Decimal
    estimate_high: Decimal
    estimate_label: str
    steps: list[dict[str, Any]]
    findings: list[FindingOut]


class ReviewIn(BaseModel):
    status: Literal["confirmed", "rejected", "needs_expert"]
    note: str | None = Field(default=None, max_length=2000)


def _policy(db: OrgDb, access: OrgAccess, policy_id: uuid.UUID) -> Policy:
    pol = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.org_id == access.org_id))
    if pol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return pol


def _policy_out(db: OrgDb, pol: Policy) -> PolicyOut:
    ids = db.scalars(
        select(Document.id).where(Document.policy_id == pol.id, Document.status != "deleted")
    )
    return PolicyOut(
        id=str(pol.id),
        carrier_name=pol.carrier_name,
        policy_number=pol.policy_number,
        state=pol.state,
        period_start=pol.period_start,
        period_end=pol.period_end,
        document_ids=[str(i) for i in ids],
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_policy(body: PolicyIn, access: CurrentOrg, db: OrgDb) -> PolicyOut:
    if access.access == "reviewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only access")
    if body.period_end <= body.period_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "period end before start")
    juris = db.get(JurisdictionPolicy, body.state)
    if juris is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown state")
    if juris.monopolistic or not juris.free_scan_allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "code": "jurisdiction_not_supported",
                "message": f"{juris.name} workers' comp is provided by a state fund, which "
                "CompBack "
                "does not support. We're sorry we can't help with this policy.",
            },
        )
    pol = Policy(org_id=access.org_id, created_by=access.principal.user_id, **body.model_dump())
    db.add(pol)
    db.flush()
    audit.record(
        db,
        action="policy.created",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="policy",
        target_id=pol.id,
    )
    return _policy_out(db, pol)


@router.get("")
def list_policies(access: CurrentOrg, db: OrgDb) -> list[PolicyOut]:
    rows = db.scalars(
        select(Policy).where(Policy.org_id == access.org_id).order_by(Policy.period_start.desc())
    )
    return [_policy_out(db, p) for p in rows]


@router.post("/{policy_id}/documents/{doc_id}")
def attach_document(
    policy_id: uuid.UUID, doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb
) -> PolicyOut:
    pol = _policy(db, access, policy_id)
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == access.org_id))
    if doc is None or doc.status == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    doc.policy_id = pol.id
    return _policy_out(db, pol)


def _finding_out(f: Finding) -> FindingOut:
    return FindingOut(
        id=str(f.id),
        detector=f.detector,
        rule_id=f.rule_id,
        rule_status=f.rule_status,
        citations=f.citations,
        title=f.title,
        explanation=f.explanation,
        conditions=f.conditions,
        evidence=f.evidence,
        impact_low=f.impact_low,
        impact_high=f.impact_high,
        confidence=f.confidence,
        priority_score=f.priority_score,
        customer_visible=f.customer_visible,
        reviewer_status=f.reviewer_status,
        reviewer_note=f.reviewer_note,
    )


def _analysis_out(db: OrgDb, access: OrgAccess, rec: Recomputation) -> AnalysisOut:
    rows = list(
        db.scalars(
            select(Finding)
            .where(Finding.recomputation_id == rec.id)
            .order_by(Finding.priority_score.desc())
        )
    )
    if access.access != "reviewer":
        rows = [f for f in rows if f.customer_visible]  # candidates are internal only
    return AnalysisOut(
        recomputation_id=str(rec.id),
        created_at=rec.created_at,
        engine_version=rec.engine_version,
        registry_version=rec.registry_version,
        billed_total=rec.billed_total,
        recomputed_total=rec.recomputed_total,
        estimate_low=rec.estimate_low,
        estimate_high=rec.estimate_high,
        estimate_label="Estimated range, not guaranteed. Findings are reviewed before any "
        "dispute is prepared.",
        steps=rec.steps,
        findings=[_finding_out(f) for f in rows],
    )


@router.post("/{policy_id}/analyze", status_code=status.HTTP_201_CREATED)
def run_analysis(policy_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> AnalysisOut:
    pol = _policy(db, access, policy_id)
    docs = list(
        db.scalars(select(Document).where(Document.policy_id == pol.id, Document.status == "ready"))
    )
    sources: list[tuple[str, str, dict[str, Any]]] = []
    ext_ids = []
    for doc in docs:
        ext = db.scalar(
            select(Extraction)
            .where(Extraction.document_id == doc.id)
            .order_by(Extraction.created_at.desc())
            .limit(1)
        )
        if ext is None:
            continue
        if ext.status not in USABLE:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "code": "verification_required",
                    "document_id": str(doc.id),
                    "message": "Some extracted values need confirmation before analysis.",
                },
            )
        sources.append((str(doc.id), ext.doc_type, ext.data))
        ext_ids.append(str(ext.id))
    ctx = build_context(pol.state, sources)
    if ctx is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "audit_required",
                "message": "Upload the premium audit statement or final audit bill for this "
                "policy.",
            },
        )
    result = analyze(ctx)
    rec = Recomputation(
        org_id=access.org_id,
        policy_id=pol.id,
        engine_version=result.recomputation.engine_version,
        registry_version=result.recomputation.registry_version,
        inputs_hash=result.inputs_hash,
        source_extraction_ids=ext_ids,
        steps=[
            {"label": s.label, "formula": s.formula, "result": str(s.result), "rule_id": s.rule_id}
            for s in result.recomputation.steps
        ],
        billed_total=result.billed.total,
        recomputed_total=result.recomputation.total,
        estimate_low=result.estimate_low,
        estimate_high=result.estimate_high,
    )
    db.add(rec)
    db.flush()
    for f in result.findings:
        db.add(
            Finding(
                org_id=access.org_id,
                policy_id=pol.id,
                recomputation_id=rec.id,
                detector=f.detector,
                rule_id=f.rule.id,
                rule_status=f.rule.status.value,
                citations=[
                    {
                        **asdict(c),
                        "effective_from": str(c.effective_from),
                        "retrieved": str(c.retrieved),
                    }
                    for c in f.rule.citations
                ],
                title=f.title,
                explanation=f.explanation,
                conditions=f.conditions,
                evidence=[asdict(e) for e in f.evidence],
                impact_low=f.impact_low,
                impact_high=f.impact_high,
                confidence=f.confidence,
                priority_score=priority_score(
                    f.detector, f.impact_low, f.impact_high, f.confidence
                ),
                customer_visible=f.customer_visible,
                reviewer_status="pending" if f.customer_visible else "needs_expert",
            )
        )
    db.flush()
    audit.record(
        db,
        action="analysis.run",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="policy",
        target_id=pol.id,
        details={"findings": len(result.findings), "inputs_hash": result.inputs_hash},
    )
    return _analysis_out(db, access, rec)


@router.get("/{policy_id}/analysis")
def latest_analysis(policy_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> AnalysisOut:
    pol = _policy(db, access, policy_id)
    rec = db.scalar(
        select(Recomputation)
        .where(Recomputation.policy_id == pol.id)
        .order_by(Recomputation.created_at.desc())
        .limit(1)
    )
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no analysis yet")
    return _analysis_out(db, access, rec)


@router.post("/{policy_id}/findings/{finding_id}/review")
def review_finding(
    policy_id: uuid.UUID, finding_id: uuid.UUID, body: ReviewIn, access: CurrentOrg, db: OrgDb
) -> FindingOut:
    """Reviewer (platform staff with a JIT grant) confirms or rejects a finding."""
    if access.access != "reviewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "reviewers only")
    f = db.scalar(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.policy_id == policy_id,
            Finding.org_id == access.org_id,
        )
    )
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if body.status == "confirmed" and not f.customer_visible:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "candidate-rule findings cannot be confirmed for customers"
        )
    f.reviewer_status, f.reviewer_note = body.status, body.note
    f.reviewed_by, f.reviewed_at = access.principal.user_id, utcnow()
    audit.record(
        db,
        action="finding.reviewed",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind="reviewer",
        target_type="finding",
        target_id=f.id,
        details={"status": body.status},
    )
    return _finding_out(f)

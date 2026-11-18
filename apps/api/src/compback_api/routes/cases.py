"""Cases: dispute package, customer approval, submission record, carrier response, outcomes, fees.

The platform never sends anything to a carrier. "Submit" records what the customer (or their own
advisor) did, when and how.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from compback_api.billing import WebhookSignatureError, billing_from_settings
from compback_api.deps import CurrentOrg, OrgAccess, OrgDb, utcnow
from compback_core import audit
from compback_core.config import get_settings
from compback_core.db import tenant_session
from compback_core.models import (
    Case,
    CaseEvent,
    DisputePackage,
    Document,
    Fee,
    Finding,
    JurisdictionPolicy,
    Organization,
    Outcome,
    Policy,
    Recomputation,
    StripeEvent,
)
from compback_disputes.package import (
    PackageInput,
    PackageItem,
    content_hash,
    render_docx,
    render_pdf,
)
from compback_disputes.workflow import (
    InvalidTransitionError,
    analysis_fee,
    check_transition,
    contingency_fee,
)
from compback_vault.service import Vault

router = APIRouter(prefix="/orgs/{org_id}/cases", tags=["cases"])
webhook_router = APIRouter(tags=["billing"])

DEADLINE_UNKNOWN = "Unknown — check your policy or the carrier's audit notice for the deadline."


class CaseIn(BaseModel):
    policy_id: uuid.UUID


class DeadlineIn(BaseModel):
    deadline_date: date
    source: str = Field(min_length=10, max_length=500, description="Where this date comes from")


class SubmitIn(BaseModel):
    method: Literal["email", "mail", "portal", "fax", "broker"]
    submitted_on: date
    note: str | None = Field(default=None, max_length=1000)


class ResponseIn(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class OutcomeIn(BaseModel):
    kind: Literal["refund", "credit", "denied", "partial"]
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    received_on: date | None = None
    proof_document_id: uuid.UUID | None = None


class FeeOut(BaseModel):
    id: str | None
    kind: str
    amount: Decimal
    status: str
    lines: list[str]
    hosted_invoice_url: str | None = None


class CaseOut(BaseModel):
    id: str
    policy_id: str
    status: str
    submitter_mode: str
    deadline: str
    deadline_source: str | None
    submitted_at: datetime | None
    submission_method: str | None
    resolution: str | None
    events: list[dict[str, Any]]
    packages: list[dict[str, Any]]
    outcomes: list[dict[str, Any]]
    fees: list[FeeOut]
    fee_preview: list[str]


def _case(db: OrgDb, access: OrgAccess, case_id: uuid.UUID) -> Case:
    row = db.scalar(select(Case).where(Case.id == case_id, Case.org_id == access.org_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return row


def _transition(
    db: OrgDb, access: OrgAccess, case: Case, target: str, note: str | None = None
) -> None:
    try:
        check_transition(case.status, target)
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.add(
        CaseEvent(
            org_id=case.org_id,
            case_id=case.id,
            kind="transition",
            from_status=case.status,
            to_status=target,
            note=note,
            actor_user_id=access.principal.user_id,
        )
    )
    audit.record(
        db,
        action="case.transition",
        org_id=case.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="case",
        target_id=case.id,
        details={"from": case.status, "to": target},
    )
    case.status = target


def _confirmed_findings(db: OrgDb, case: Case) -> list[Finding]:
    return list(
        db.scalars(
            select(Finding)
            .where(
                Finding.recomputation_id == case.recomputation_id,
                Finding.customer_visible.is_(True),
                Finding.reviewer_status == "confirmed",
            )
            .order_by(Finding.priority_score.desc())
        )
    )


def _verified_recovery(db: OrgDb, case: Case) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(Outcome.amount), 0)).where(
            Outcome.case_id == case.id, Outcome.verified_at.is_not(None), Outcome.kind != "denied"
        )
    ) or Decimal(0)


def _fee_preview(db: OrgDb, case: Case) -> list[str]:
    s = get_settings()
    estimate_high = sum((f.impact_high for f in _confirmed_findings(db, case)), Decimal(0))
    quote = contingency_fee(
        estimate_high,
        s.contingency_rate,
        s.contingency_cap_usd,
        s.analysis_fee_usd,
        s.credit_analysis_fee_against_contingency,
    )
    return [
        *analysis_fee(s.analysis_fee_usd).lines,
        f"Contingency: {s.contingency_rate * 100:.0f}% of refunds or credits you actually "
        f"receive and we verify, capped at ${s.contingency_cap_usd:,.2f}, less the analysis "
        "fee.",
        "Example if the full estimate were recovered (not guaranteed): "
        + quote.lines[-1].replace("Contingency fee due", "fee"),
    ]


def _out(db: OrgDb, case: Case) -> CaseOut:
    events = db.scalars(
        select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)
    )
    pkgs = db.scalars(
        select(DisputePackage)
        .where(DisputePackage.case_id == case.id)
        .order_by(DisputePackage.version)
    )
    outs = db.scalars(select(Outcome).where(Outcome.case_id == case.id))
    fees = db.scalars(select(Fee).where(Fee.case_id == case.id))
    return CaseOut(
        id=str(case.id),
        policy_id=str(case.policy_id),
        status=case.status,
        submitter_mode=case.submitter_mode,
        deadline=case.deadline_date.isoformat() if case.deadline_date else DEADLINE_UNKNOWN,
        deadline_source=case.deadline_source,
        submitted_at=case.submitted_at,
        submission_method=case.submission_method,
        resolution=case.resolution,
        events=[
            {
                "kind": e.kind,
                "from": e.from_status,
                "to": e.to_status,
                "note": e.note,
                "at": e.created_at.isoformat(),
            }
            for e in events
        ],
        packages=[
            {
                "id": str(p.id),
                "version": p.version,
                "total_low": str(p.total_low),
                "total_high": str(p.total_high),
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            }
            for p in pkgs
        ],
        outcomes=[
            {
                "id": str(o.id),
                "kind": o.kind,
                "amount": str(o.amount),
                "verified": o.verified_at is not None,
            }
            for o in outs
        ],
        fees=[
            FeeOut(
                id=str(f.id),
                kind=f.kind,
                amount=f.amount,
                status=f.status,
                lines=f.calculation.get("lines", []),
                hosted_invoice_url=f.hosted_invoice_url,
            )
            for f in fees
        ],
        fee_preview=_fee_preview(db, case),
    )


def _writer(access: OrgAccess) -> None:
    if access.access not in ("member", "advisor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "customer or advisor action")


@router.post("", status_code=status.HTTP_201_CREATED)
def open_case(body: CaseIn, access: CurrentOrg, db: OrgDb) -> CaseOut:
    _writer(access)
    pol = db.scalar(
        select(Policy).where(Policy.id == body.policy_id, Policy.org_id == access.org_id)
    )
    if pol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    juris = db.get(JurisdictionPolicy, pol.state)
    if juris is None or not juris.paid_analysis_allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "not_available_in_state",
                "message": "Dispute packages are not available for policies in this state yet. "
                "Your free scan results remain available.",
            },
        )
    rec = db.scalar(
        select(Recomputation)
        .where(Recomputation.policy_id == pol.id)
        .order_by(Recomputation.created_at.desc())
        .limit(1)
    )
    if rec is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "run an analysis first")
    case = Case(
        org_id=access.org_id,
        policy_id=pol.id,
        recomputation_id=rec.id,
        submitter_mode=juris.submitter_mode,
        created_by=access.principal.user_id,
    )
    db.add(case)
    db.flush()
    db.add(
        CaseEvent(
            org_id=access.org_id,
            case_id=case.id,
            kind="opened",
            to_status="draft",
            actor_user_id=access.principal.user_id,
        )
    )
    audit.record(
        db,
        action="case.opened",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="case",
        target_id=case.id,
    )
    return _out(db, case)


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> CaseOut:
    return _out(db, _case(db, access, case_id))


@router.post("/{case_id}/deadline")
def set_deadline(case_id: uuid.UUID, body: DeadlineIn, access: CurrentOrg, db: OrgDb) -> CaseOut:
    """Deadlines are stored only with a stated source (e.g. 'carrier audit notice dated ...')."""
    case = _case(db, access, case_id)
    case.deadline_date, case.deadline_source = body.deadline_date, body.source
    db.add(
        CaseEvent(
            org_id=case.org_id,
            case_id=case.id,
            kind="deadline_set",
            note=f"{body.deadline_date}: {body.source}",
            actor_user_id=access.principal.user_id,
        )
    )
    return _out(db, case)


@router.post("/{case_id}/package", status_code=status.HTTP_201_CREATED)
def build_package(case_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> CaseOut:
    case = _case(db, access, case_id)
    if case.status not in ("draft", "ready_for_review"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"case is {case.status}")
    findings = _confirmed_findings(db, case)
    if not findings:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "no_confirmed_findings",
                "message": "A reviewer must confirm at least one finding first.",
            },
        )
    pol = db.get(Policy, case.policy_id)
    org = db.get(Organization, case.org_id)
    assert pol is not None
    assert org is not None
    items = []
    for f in findings:
        ev = (
            "; ".join(
                f"document {e['document_id'][:8]}, page {e['page'] or '?'}" for e in f.evidence
            )
            or "carrier audit statement"
        )
        cite = (
            "; ".join(f"{c['source']} {c['section']}".strip() for c in f.citations)
            or "Consistency of the carrier's own documents"
        )
        items.append(
            PackageItem(str(f.id), f.title, f.explanation, f.impact_low, f.impact_high, ev, cite)
        )
    inp = PackageInput(
        org.name,
        pol.carrier_name,
        pol.policy_number,
        f"{pol.period_start:%m/%d/%Y} - {pol.period_end:%m/%d/%Y}",
        utcnow().date(),
        items,
    )
    pdf, docx = render_pdf(inp), render_docx(inp)
    version = (
        db.scalar(select(func.max(DisputePackage.version)).where(DisputePackage.case_id == case.id))
        or 0
    ) + 1
    vault = Vault.from_settings()
    base = f"orgs/{case.org_id}/cases/{case.id}/package-v{version}"
    vault.store.put(f"{base}.pdf", vault.envelope.encrypt(pdf, f"package:{case.id}:{version}:pdf"))
    vault.store.put(
        f"{base}.docx", vault.envelope.encrypt(docx, f"package:{case.id}:{version}:docx")
    )
    low = sum((i.impact_low for i in items), Decimal(0))
    high = sum((i.impact_high for i in items), Decimal(0))
    db.add(
        DisputePackage(
            org_id=case.org_id,
            case_id=case.id,
            version=version,
            finding_ids=[i.finding_id for i in items],
            total_low=low,
            total_high=high,
            content_sha256=content_hash(inp),
            pdf_key=f"{base}.pdf",
            docx_key=f"{base}.docx",
        )
    )
    if case.status == "draft":
        _transition(db, access, case, "ready_for_review", f"package v{version} generated")
    return _out(db, case)


@router.get("/{case_id}/package/{version}.{fmt}")
def download_package(
    case_id: uuid.UUID, version: int, fmt: Literal["pdf", "docx"], access: CurrentOrg, db: OrgDb
) -> Response:
    case = _case(db, access, case_id)
    pkg = db.scalar(
        select(DisputePackage).where(
            DisputePackage.case_id == case.id, DisputePackage.version == version
        )
    )
    if pkg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    vault = Vault.from_settings()
    key = pkg.pdf_key if fmt == "pdf" else pkg.docx_key
    data = vault.envelope.decrypt(vault.store.get(key), f"package:{case.id}:{version}:{fmt}")
    audit.record(
        db,
        action="package.downloaded",
        org_id=case.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="dispute_package",
        target_id=pkg.id,
        details={"fmt": fmt},
    )
    media = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(
        data,
        media_type=media,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="dispute-package-v{version}.{fmt}"',
        },
    )


@router.post("/{case_id}/approve")
def approve(case_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> CaseOut:
    """Customer approves the latest package and accepts the fee terms shown in ``fee_preview``."""
    if not (access.access == "member" and access.role == "owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the business owner must approve")
    case = _case(db, access, case_id)
    pkg = db.scalar(
        select(DisputePackage)
        .where(DisputePackage.case_id == case.id)
        .order_by(DisputePackage.version.desc())
        .limit(1)
    )
    if pkg is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "generate the package first")
    pkg.approved_by, pkg.approved_at = access.principal.user_id, utcnow()
    db.add(
        CaseEvent(
            org_id=case.org_id,
            case_id=case.id,
            kind="fee_terms_accepted",
            note=" | ".join(_fee_preview(db, case)),
            actor_user_id=access.principal.user_id,
        )
    )
    _transition(db, access, case, "approved_by_customer", f"package v{pkg.version} approved")
    return _out(db, case)


@router.post("/{case_id}/submitted")
def record_submission(case_id: uuid.UUID, body: SubmitIn, access: CurrentOrg, db: OrgDb) -> CaseOut:
    _writer(access)
    case = _case(db, access, case_id)
    if case.submitter_mode == "customer_only" and access.access != "member":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the policyholder must submit in this state")
    case.submitted_at = datetime.combine(
        body.submitted_on, datetime.min.time(), tzinfo=utcnow().tzinfo
    )
    case.submitted_by, case.submission_method = access.principal.user_id, body.method
    _transition(db, access, case, "submitted", body.note)
    return _out(db, case)


@router.post("/{case_id}/carrier-response")
def carrier_response(
    case_id: uuid.UUID, body: ResponseIn, access: CurrentOrg, db: OrgDb
) -> CaseOut:
    _writer(access)
    case = _case(db, access, case_id)
    if case.status == "carrier_responded":
        db.add(
            CaseEvent(
                org_id=case.org_id,
                case_id=case.id,
                kind="carrier_contact",
                note=body.note,
                actor_user_id=access.principal.user_id,
            )
        )
    else:
        _transition(db, access, case, "carrier_responded", body.note)
    return _out(db, case)


@router.post("/{case_id}/outcomes", status_code=status.HTTP_201_CREATED)
def record_outcome(case_id: uuid.UUID, body: OutcomeIn, access: CurrentOrg, db: OrgDb) -> CaseOut:
    _writer(access)
    case = _case(db, access, case_id)
    if body.kind != "denied" and body.proof_document_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "upload the refund/credit notice and attach it as proof",
        )
    if (
        body.proof_document_id is not None
        and db.scalar(
            select(Document.id).where(
                Document.id == body.proof_document_id, Document.org_id == case.org_id
            )
        )
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proof document not found")
    db.add(
        Outcome(
            org_id=case.org_id,
            case_id=case.id,
            kind=body.kind,
            amount=body.amount,
            received_on=body.received_on,
            proof_document_id=body.proof_document_id,
            recorded_by=access.principal.user_id,
        )
    )
    case.resolution = body.kind
    if case.status == "carrier_responded":
        _transition(db, access, case, "resolved", f"{body.kind}: {body.amount}")
    return _out(db, case)


@router.post("/{case_id}/outcomes/{outcome_id}/verify")
def verify_outcome(
    case_id: uuid.UUID, outcome_id: uuid.UUID, access: CurrentOrg, db: OrgDb
) -> CaseOut:
    """A reviewer checks the proof document before any contingency fee can be invoiced."""
    if access.access != "reviewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "reviewers only")
    case = _case(db, access, case_id)
    out = db.scalar(select(Outcome).where(Outcome.id == outcome_id, Outcome.case_id == case.id))
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    out.verified_by, out.verified_at = access.principal.user_id, utcnow()
    audit.record(
        db,
        action="outcome.verified",
        org_id=case.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind="reviewer",
        target_type="outcome",
        target_id=out.id,
        details={"amount": str(out.amount)},
    )
    return _out(db, case)


@router.post("/{case_id}/fees/contingency", status_code=status.HTTP_201_CREATED)
def invoice_contingency(case_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> CaseOut:
    if not (access.access == "member" and access.role == "owner") and access.access != "reviewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not allowed")
    case = _case(db, access, case_id)
    if case.status != "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "case must be resolved")
    recovery = _verified_recovery(db, case)
    if recovery <= 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "no_verified_recovery",
                "message": "No verified refund or credit; no contingency fee is due.",
            },
        )
    s = get_settings()
    paid_analysis = db.scalar(
        select(func.coalesce(func.sum(Fee.amount), 0)).where(
            Fee.case_id == case.id, Fee.kind == "analysis", Fee.status == "paid"
        )
    ) or Decimal(0)
    quote = contingency_fee(
        Decimal(recovery),
        s.contingency_rate,
        s.contingency_cap_usd,
        Decimal(paid_analysis),
        s.credit_analysis_fee_against_contingency,
    )
    fee = Fee(
        org_id=case.org_id,
        case_id=case.id,
        kind="contingency",
        basis_amount=quote.basis_amount,
        rate=quote.rate,
        credit_applied=quote.credit_applied,
        cap=quote.cap,
        amount=quote.amount,
        calculation={"lines": quote.lines},
    )
    db.add(fee)
    db.flush()
    org = db.get(Organization, case.org_id)
    assert org is not None
    if quote.amount > 0:
        result = billing_from_settings().create_invoice(
            fee_id=str(fee.id),
            customer_id=org.billing_customer_id,
            email=access.principal.email,
            org_name=org.name,
            description=f"CompBack contingency fee — case {str(case.id)[:8]}",
            amount=quote.amount,
        )
        org.billing_customer_id = result.customer_id
        fee.status, fee.stripe_invoice_id = "invoiced", result.invoice_id
        fee.hosted_invoice_url = result.hosted_url
    else:
        fee.status = "void"
    _transition(db, access, case, "fee_invoiced", quote.lines[-1])
    return _out(db, case)


@router.post("/{case_id}/fees/analysis", status_code=status.HTTP_201_CREATED)
def invoice_analysis(case_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> CaseOut:
    """Flat analysis fee, invoiced after the customer approved the package and fee terms."""
    if not (access.access == "member" and access.role == "owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the business owner must approve fees")
    case = _case(db, access, case_id)
    if case.status not in ("approved_by_customer", "submitted", "carrier_responded"):
        raise HTTPException(status.HTTP_409_CONFLICT, "approve the package first")
    if (
        db.scalar(
            select(Fee.id).where(
                Fee.case_id == case.id, Fee.kind == "analysis", Fee.status != "void"
            )
        )
        is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "analysis fee already invoiced")
    quote = analysis_fee(get_settings().analysis_fee_usd)
    fee = Fee(
        org_id=case.org_id,
        case_id=case.id,
        kind="analysis",
        basis_amount=quote.amount,
        amount=quote.amount,
        calculation={"lines": quote.lines},
    )
    db.add(fee)
    db.flush()
    org = db.get(Organization, case.org_id)
    assert org is not None
    result = billing_from_settings().create_invoice(
        fee_id=str(fee.id),
        customer_id=org.billing_customer_id,
        email=access.principal.email,
        org_name=org.name,
        description="CompBack full analysis and dispute package",
        amount=quote.amount,
    )
    org.billing_customer_id = result.customer_id
    fee.status, fee.stripe_invoice_id, fee.hosted_invoice_url = (
        "invoiced",
        result.invoice_id,
        result.hosted_url,
    )
    audit.record(
        db,
        action="fee.invoiced",
        org_id=case.org_id,
        actor_user_id=access.principal.user_id,
        target_type="fee",
        target_id=fee.id,
        details={"kind": "analysis", "amount": str(quote.amount)},
    )
    return _out(db, case)


@webhook_router.post("/billing/stripe/webhook")
async def stripe_webhook(
    request: Request, stripe_signature: Annotated[str | None, Header()] = None
) -> dict[str, str]:
    payload = await request.body()
    try:
        event = billing_from_settings().parse_webhook(payload, stripe_signature)
    except WebhookSignatureError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid signature") from exc
    event_id, kind = str(event.get("id")), str(event.get("type"))
    obj = event.get("data", {}).get("object", {})
    with tenant_session(None, None, actor_kind="system") as db:
        if db.get(StripeEvent, event_id) is not None:
            return {"status": "duplicate"}
        db.add(StripeEvent(id=event_id, type=kind))
        new_status = {
            "invoice.paid": "paid",
            "invoice.voided": "void",
            "invoice.marked_uncollectible": "void",
        }.get(kind)
        if new_status and obj.get("id"):
            fee = db.scalar(select(Fee).where(Fee.stripe_invoice_id == obj["id"]))
            if fee is not None:
                fee.status = new_status
                audit.record(
                    db,
                    action=f"fee.{new_status}",
                    org_id=fee.org_id,
                    actor_user_id=None,
                    actor_kind="system",
                    target_type="fee",
                    target_id=fee.id,
                    details={"stripe_event": event_id},
                )
        elif kind.startswith("charge.dispute"):
            audit.record(
                db,
                action="billing.dispute_event",
                org_id=None,
                actor_user_id=None,
                actor_kind="system",
                details={"stripe_event": event_id, "type": kind},
            )
    return {"status": "ok"}

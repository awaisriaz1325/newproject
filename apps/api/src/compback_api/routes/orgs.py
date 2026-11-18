"""Organization-scoped endpoints: profile, advisor links + consent, JIT reviewer access, audit."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, text

from compback_api.deps import (
    CurrentOrg,
    CurrentPrincipal,
    OrgDb,
    enforce_mfa,
    require_owner,
    utcnow,
)
from compback_core import audit
from compback_core.db import tenant_session
from compback_core.models import AccessGrant, AdvisorClientLink, AuditLog, Consent, Organization

router = APIRouter(prefix="/orgs/{org_id}", tags=["organizations"])

ADVISOR_CONSENT_VERSION = "2026-11-18-draft"
CUSTOMER_VISIBLE_ACTIONS = (
    "document.viewed",
    "document.downloaded",
    "access_grant.created",
    "access_grant.revoked",
    "advisor_link.requested",
    "advisor_link.approved",
    "advisor_link.revoked",
)
MAX_GRANT_MINUTES = 240


class OrgOut(BaseModel):
    id: str
    name: str
    kind: str
    access: str
    role: str
    invite_code: str | None


class LinkRequestIn(BaseModel):
    invite_code: str = Field(min_length=6, max_length=16)


class LinkOut(BaseModel):
    id: str
    advisor_org_id: str
    advisor_org_name: str | None
    client_org_id: str
    client_org_name: str | None
    status: str
    approved_at: datetime | None
    revoked_at: datetime | None


class GrantIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
    minutes: int = Field(default=60, ge=5, le=MAX_GRANT_MINUTES)


class GrantOut(BaseModel):
    id: str
    expires_at: datetime


class AuditEntryOut(BaseModel):
    seq: int
    action: str
    actor_kind: str
    actor_user_id: str | None
    target_type: str | None
    target_id: str | None
    reason: str | None
    details: dict[str, Any]
    created_at: datetime


class ChainOut(BaseModel):
    ok: bool
    entries: int
    broken_at_seq: int | None


@router.get("")
def get_org(access: CurrentOrg, db: OrgDb) -> OrgOut:
    org = db.get(Organization, access.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    show_code = access.access == "member" and access.role == "owner" and org.kind == "employer"
    return OrgOut(
        id=str(org.id),
        name=org.name,
        kind=org.kind,
        access=access.access,
        role=access.role,
        invite_code=org.invite_code if show_code else None,
    )


def _link_out(db: OrgDb, link: AdvisorClientLink, names: dict[uuid.UUID, str]) -> LinkOut:
    return LinkOut(
        id=str(link.id),
        advisor_org_id=str(link.advisor_org_id),
        advisor_org_name=names.get(link.advisor_org_id),
        client_org_id=str(link.client_org_id),
        client_org_name=names.get(link.client_org_id),
        status=link.status,
        approved_at=link.approved_at,
        revoked_at=link.revoked_at,
    )


@router.post("/advisor-links", status_code=status.HTTP_201_CREATED)
def request_link(body: LinkRequestIn, access: CurrentOrg, db: OrgDb) -> LinkOut:
    """An advisor firm requests access to an employer using the employer's invite code."""
    if (
        access.org_kind != "advisor_firm"
        or access.access != "member"
        or access.role not in ("owner", "advisor")
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only advisor firm members can request")
    target = db.execute(
        text("SELECT id, name FROM compback.find_org_by_invite_code(:c)"),
        {"c": body.invite_code.strip().upper()},
    ).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no employer with that code")
    existing = db.scalar(
        select(AdvisorClientLink).where(
            AdvisorClientLink.advisor_org_id == access.org_id,
            AdvisorClientLink.client_org_id == target.id,
            AdvisorClientLink.status != "revoked",
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "link already exists")
    link = AdvisorClientLink(
        advisor_org_id=access.org_id,
        client_org_id=target.id,
        status="pending",
        requested_by=access.principal.user_id,
        scope={"documents": "read", "cases": "manage"},
    )
    db.add(link)
    db.flush()
    audit.record(
        db,
        action="advisor_link.requested",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="advisor_link",
        target_id=link.id,
    )
    return _link_out(db, link, {access.org_id: access.org_name, target.id: target.name})


@router.get("/advisor-links")
def list_links(access: CurrentOrg, db: OrgDb) -> list[LinkOut]:
    links = list(
        db.scalars(
            select(AdvisorClientLink)
            .where(
                or_(
                    AdvisorClientLink.advisor_org_id == access.org_id,
                    AdvisorClientLink.client_org_id == access.org_id,
                )
            )
            .order_by(AdvisorClientLink.created_at.desc())
        )
    )
    if access.access != "member":
        links = [l for l in links if l.advisor_org_id == access.org_id]  # noqa: E741
    other_ids = {l.advisor_org_id for l in links} | {l.client_org_id for l in links}  # noqa: E741
    names = _org_names_for_links(other_ids, access.org_id, access.principal.user_id)
    return [_link_out(db, link, names) for link in links]


def _org_names_for_links(
    ids: set[uuid.UUID], org_id: uuid.UUID, user_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    # Names of linked orgs are shared with the counterparty (needed to approve/revoke).
    if not ids:
        return {}
    with tenant_session(org_id, user_id, actor_kind="system") as db:
        rows = db.execute(
            text(
                "SELECT o.id, o.name FROM organizations o WHERE o.id = ANY(:ids) AND EXISTS ("
                " SELECT 1 FROM advisor_client_links l WHERE (l.advisor_org_id = o.id AND"
                " l.client_org_id = :org) OR (l.client_org_id = o.id AND l.advisor_org_id = :org)"
                " OR o.id = :org)"
            ),
            {"ids": list(ids), "org": org_id},
        ).all()
    return {r.id: r.name for r in rows}


def _get_link(db: OrgDb, link_id: uuid.UUID, org_id: uuid.UUID) -> AdvisorClientLink:
    link = db.scalar(
        select(AdvisorClientLink).where(
            AdvisorClientLink.id == link_id,
            or_(
                AdvisorClientLink.advisor_org_id == org_id,
                AdvisorClientLink.client_org_id == org_id,
            ),
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return link


@router.post("/advisor-links/{link_id}/approve")
def approve_link(link_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> LinkOut:
    """Only the employer's owner can grant an advisor firm access (explicit consent)."""
    require_owner(access)
    link = _get_link(db, link_id, access.org_id)
    if link.client_org_id != access.org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the client can approve")
    if link.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"link is {link.status}")
    now = utcnow()
    link.status, link.approved_by, link.approved_at = "active", access.principal.user_id, now
    db.add(
        Consent(
            org_id=access.org_id,
            user_id=access.principal.user_id,
            kind="advisor_access",
            version=ADVISOR_CONSENT_VERSION,
            details={
                "advisor_org_id": str(link.advisor_org_id),
                "link_id": str(link.id),
                "scope": link.scope,
            },
        )
    )
    audit.record(
        db,
        action="advisor_link.approved",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="advisor_link",
        target_id=link.id,
    )
    return _link_out(db, link, {})


@router.post("/advisor-links/{link_id}/revoke")
def revoke_link(link_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> LinkOut:
    """Either side's owner may revoke. Access ends immediately (checked on every request)."""
    if access.access != "member" or access.role not in ("owner", "advisor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not allowed")
    link = _get_link(db, link_id, access.org_id)
    if link.client_org_id == access.org_id and access.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner role required")
    if link.status == "revoked":
        raise HTTPException(status.HTTP_409_CONFLICT, "already revoked")
    now = utcnow()
    link.status, link.revoked_by, link.revoked_at = "revoked", access.principal.user_id, now
    if link.client_org_id == access.org_id:
        consents = db.scalars(
            select(Consent).where(
                Consent.org_id == access.org_id,
                Consent.kind == "advisor_access",
                Consent.revoked_at.is_(None),
            )
        )
        for consent in consents:
            if consent.details.get("link_id") == str(link.id):
                consent.revoked_at = now
    audit.record(
        db,
        action="advisor_link.revoked",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        target_type="advisor_link",
        target_id=link.id,
    )
    return _link_out(db, link, {})


@router.post("/access-grants", status_code=status.HTTP_201_CREATED)
def create_grant(org_id: uuid.UUID, body: GrantIn, principal: CurrentPrincipal) -> GrantOut:
    """Just-in-time reviewer access: platform staff only, MFA verified, reason required, expiring.

    Not behind ``CurrentOrg`` because the reviewer has no access until this grant exists.
    """
    enforce_mfa(principal)
    if not principal.is_platform_staff:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    with tenant_session(org_id, principal.user_id, actor_kind="system") as check:
        target = check.get(Organization, org_id)
        if target is None or target.kind == "platform":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    expires = utcnow() + timedelta(minutes=body.minutes)
    with tenant_session(org_id, principal.user_id) as db:
        grant = AccessGrant(
            org_id=org_id, grantee_user_id=principal.user_id, reason=body.reason, expires_at=expires
        )
        db.add(grant)
        db.flush()
        audit.record(
            db,
            action="access_grant.created",
            org_id=org_id,
            actor_user_id=principal.user_id,
            actor_kind="reviewer",
            target_type="access_grant",
            target_id=grant.id,
            reason=body.reason,
            details={"minutes": body.minutes},
        )
        return GrantOut(id=str(grant.id), expires_at=grant.expires_at)


def _entries(db: OrgDb, org_id: uuid.UUID, actions: tuple[str, ...] | None) -> list[AuditEntryOut]:
    stmt = select(AuditLog).where(AuditLog.org_id == org_id)
    if actions is not None:
        stmt = stmt.where(AuditLog.action.in_(actions))
    rows = db.scalars(stmt.order_by(AuditLog.seq.desc()).limit(500))
    return [
        AuditEntryOut(
            seq=r.seq,
            action=r.action,
            actor_kind=r.actor_kind,
            actor_user_id=str(r.actor_user_id) if r.actor_user_id else None,
            target_type=r.target_type,
            target_id=r.target_id,
            reason=r.reason,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/access-log")
def access_log(access: CurrentOrg, db: OrgDb) -> list[AuditEntryOut]:
    """Customer-visible log of who accessed this organization's data and why."""
    if access.access != "member":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "members only")
    return _entries(db, access.org_id, CUSTOMER_VISIBLE_ACTIONS)


@router.get("/audit")
def full_audit(access: CurrentOrg, db: OrgDb) -> list[AuditEntryOut]:
    require_owner(access)
    return _entries(db, access.org_id, None)


@router.get("/audit/verify")
def verify_audit(access: CurrentOrg, db: OrgDb) -> ChainOut:
    require_owner(access)
    result = audit.verify_chain(db, access.org_id)
    return ChainOut(ok=result.ok, entries=result.entries, broken_at_seq=result.broken_at_seq)

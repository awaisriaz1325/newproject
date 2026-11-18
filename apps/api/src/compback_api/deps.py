"""Request dependencies: principal (session cookie), CSRF, rate limits, org access + MFA policy.

Tenant isolation is enforced twice: the app checks access explicitly here, and every query then
runs in a transaction whose ``app.org_id``/``app.user_id`` drive Postgres RLS.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Path, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from compback_api.security import token_digest
from compback_core.config import get_settings
from compback_core.db import tenant_session
from compback_core.models import AccessGrant, AdvisorClientLink, Membership, Organization, User
from compback_core.models import Session as DbSession

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
MFA_ROLES = {"advisor", "reviewer", "platform_admin"}


def session_cookie_name() -> str:
    # __Host- prefix requires Secure; dev over plain http uses a plain name.
    return "__Host-cb_session" if get_settings().cookie_secure else "cb_session"


CSRF_COOKIE = "cb_csrf"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    email_verified: bool
    mfa_enabled: bool
    mfa_verified: bool
    is_platform_staff: bool
    csrf_hash: bytes


def auth_db() -> Iterator[Session]:
    """Transaction for authentication flows (actor 'auth': may read users by email)."""
    with tenant_session(None, None, actor_kind="auth") as db:
        yield db


AuthDb = Annotated[Session, Depends(auth_db, scope="function")]


def _load_principal(request: Request) -> Principal | None:
    token = request.cookies.get(session_cookie_name())
    if not token:
        return None
    settings = get_settings()
    now = utcnow()
    with tenant_session(None, None, actor_kind="auth") as db:
        row = db.execute(
            select(DbSession, User)
            .join(User, User.id == DbSession.user_id)
            .where(DbSession.token_hash == token_digest(token))
        ).first()
        if row is None:
            return None
        sess, user = row
        idle_limit = sess.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
        if sess.revoked_at or sess.expires_at <= now or idle_limit <= now or user.disabled_at:
            return None
        if now - sess.last_seen_at > timedelta(minutes=1):
            sess.last_seen_at = now
        return Principal(
            user_id=user.id,
            session_id=sess.id,
            email=user.email,
            email_verified=user.email_verified_at is not None,
            mfa_enabled=user.mfa_enabled,
            mfa_verified=sess.mfa_verified,
            is_platform_staff=user.is_platform_staff,
            csrf_hash=sess.csrf_token_hash,
        )


def optional_principal(request: Request) -> Principal | None:
    return _load_principal(request)


def require_principal(
    request: Request, x_csrf_token: Annotated[str | None, Header()] = None
) -> Principal:
    principal = _load_principal(request)
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    if request.method in MUTATING and (
        not x_csrf_token or token_digest(x_csrf_token) != principal.csrf_hash
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid CSRF token")
    return principal


CurrentPrincipal = Annotated[Principal, Depends(require_principal)]


def require_csrf_header(
    request: Request, x_csrf_token: Annotated[str | None, Header()] = None
) -> None:
    """Unauthenticated mutating endpoints still require a custom header (blocks form CSRF)."""
    if request.method in MUTATING and not x_csrf_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing X-CSRF-Token header")


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    """Fixed-window limiter shared across instances (Postgres-backed, no PII stored)."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limits_enabled:
            return
        client = request.client.host if request.client else "unknown"
        key = hashlib.sha256(f"{name}:{client}".encode()).hexdigest()
        now = utcnow()
        window = datetime.fromtimestamp(
            int(now.timestamp()) // window_seconds * window_seconds, tz=UTC
        )
        with tenant_session(None, None, actor_kind="system") as db:
            count = db.execute(
                text(
                    "INSERT INTO rate_limit_counters (key, window_start, count) "
                    "VALUES (:k, :w, 1) ON CONFLICT (key, window_start) "
                    "DO UPDATE SET count = rate_limit_counters.count + 1 RETURNING count"
                ),
                {"k": key, "w": window},
            ).scalar_one()
        if count > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "too many requests, try again later",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


AccessKind = Literal["member", "advisor", "reviewer"]


@dataclass(frozen=True)
class OrgAccess:
    org_id: uuid.UUID
    org_kind: str
    org_name: str
    access: AccessKind
    role: str
    principal: Principal


def resolve_access(principal: Principal, org_id: uuid.UUID) -> OrgAccess | None:
    """Explicit application-level authorization (independent of the RLS function)."""
    now = utcnow()
    with tenant_session(org_id, principal.user_id, actor_kind="system") as db:
        org = db.get(Organization, org_id)
        if org is None:
            return None
        membership = db.scalar(
            select(Membership).where(
                Membership.org_id == org_id, Membership.user_id == principal.user_id
            )
        )
        if membership is not None:
            return OrgAccess(org.id, org.kind, org.name, "member", membership.role, principal)
        advisor_role = db.scalar(
            select(Membership.role)
            .join(AdvisorClientLink, AdvisorClientLink.advisor_org_id == Membership.org_id)
            .where(
                AdvisorClientLink.client_org_id == org_id,
                AdvisorClientLink.status == "active",
                Membership.user_id == principal.user_id,
                Membership.role.in_(("owner", "advisor")),
            )
            .limit(1)
        )
        if advisor_role is not None:
            return OrgAccess(org.id, org.kind, org.name, "advisor", "advisor", principal)
        grant = db.scalar(
            select(AccessGrant.id).where(
                AccessGrant.org_id == org_id,
                AccessGrant.grantee_user_id == principal.user_id,
                AccessGrant.revoked_at.is_(None),
                AccessGrant.expires_at > now,
            )
        )
        if grant is not None and principal.is_platform_staff:
            return OrgAccess(org.id, org.kind, org.name, "reviewer", "reviewer", principal)
    return None


def user_requires_mfa(principal: Principal) -> bool:
    if principal.is_platform_staff or principal.mfa_enabled:
        return True
    with tenant_session(None, principal.user_id) as db:
        rows = db.execute(
            select(Membership.role, Organization.kind)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == principal.user_id)
        ).all()
    return any(role in MFA_ROLES or kind == "advisor_firm" for role, kind in rows)


def enforce_mfa(principal: Principal) -> None:
    if user_requires_mfa(principal) and not principal.mfa_verified:
        detail = "mfa_required" if principal.mfa_enabled else "mfa_enrollment_required"
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)


def require_org_access(
    principal: CurrentPrincipal, org_id: Annotated[uuid.UUID, Path()]
) -> OrgAccess:
    enforce_mfa(principal)
    access = resolve_access(principal, org_id)
    if access is None:
        # 404, not 403: do not reveal whether the org exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return access


CurrentOrg = Annotated[OrgAccess, Depends(require_org_access)]


def org_db(access: CurrentOrg) -> Iterator[Session]:
    """Tenant-scoped transaction for the current request (RLS applies)."""
    with tenant_session(access.org_id, access.principal.user_id) as db:
        yield db


OrgDb = Annotated[Session, Depends(org_db, scope="function")]


def require_owner(access: OrgAccess) -> None:
    if not (access.access == "member" and access.role == "owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "owner role required")

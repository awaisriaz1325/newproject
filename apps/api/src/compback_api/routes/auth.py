"""Signup, email verification, login, MFA, logout, and the current-user view."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update

from compback_api import security
from compback_api.deps import (
    CSRF_COOKIE,
    AuthDb,
    CurrentPrincipal,
    check_rate,
    rate_limit,
    require_csrf_header,
    session_cookie_name,
    user_requires_mfa,
    utcnow,
)
from compback_core import audit
from compback_core.config import get_settings
from compback_core.db import tenant_session
from compback_core.models import (
    Consent,
    EmailOutbox,
    EmailToken,
    Membership,
    Organization,
    User,
)
from compback_core.models import Session as DbSession
from compback_vault.crypto import get_envelope

router = APIRouter(prefix="/auth", tags=["auth"])

TERMS_VERSION = "2026-11-18-draft"
LOCKOUT_THRESHOLD = 10
LOCKOUT_MINUTES = 15


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    org_name: str = Field(min_length=2, max_length=200)
    org_kind: Literal["employer", "advisor_firm"] = "employer"
    accept_terms: bool
    terms_version: str = TERMS_VERSION


class StatusOut(BaseModel):
    status: str


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class LoginOut(BaseModel):
    csrf_token: str
    mfa_required: bool
    mfa_enrollment_required: bool


class CodeIn(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    recovery_code: str | None = Field(default=None, max_length=20)


class MfaSetupOut(BaseModel):
    otpauth_uri: str


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


class MembershipOut(BaseModel):
    org_id: str
    org_name: str
    org_kind: str
    role: str


class MeOut(BaseModel):
    id: str
    email: str
    email_verified: bool
    mfa_enabled: bool
    mfa_verified: bool
    mfa_required: bool
    is_platform_staff: bool
    memberships: list[MembershipOut]


def _issue_email_token(db: AuthDb, user: User, purpose: str, hours: int) -> str:
    token = security.new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=security.token_digest(token),
            expires_at=utcnow() + timedelta(hours=hours),
        )
    )
    return token


@router.post(
    "/signup",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf_header), Depends(rate_limit("signup", 5, 300))],
)
def signup(body: SignupIn, db: AuthDb) -> StatusOut:
    """Always answers the same way whether or not the email exists (no account enumeration)."""
    if not body.accept_terms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "terms must be accepted")
    try:
        security.validate_password(body.password, body.email)
    except security.WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    # Hash before the lookup so both branches cost the same (no timing-based enumeration).
    password_hash = security.hash_password(body.password)
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        db.add(EmailOutbox(to_user_id=existing.id, template="signup_existing", payload={}))
        return StatusOut(status="check_email")

    user = User(email=body.email, password_hash=password_hash)
    org = Organization(
        kind=body.org_kind, name=body.org_name, invite_code=security.new_invite_code()
    )
    db.add_all([user, org])
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    for kind in ("terms", "data_processing"):
        db.add(Consent(org_id=org.id, user_id=user.id, kind=kind, version=body.terms_version))
    token = _issue_email_token(db, user, "verify_email", hours=24)
    db.add(EmailOutbox(to_user_id=user.id, template="verify_email", payload={"token": token}))
    db.flush()
    audit.record(
        db,
        action="org.created",
        org_id=org.id,
        actor_user_id=user.id,
        actor_kind="auth",
        target_type="organization",
        target_id=org.id,
        details={"kind": org.kind},
    )
    audit.record(
        db,
        action="consent.granted",
        org_id=org.id,
        actor_user_id=user.id,
        actor_kind="auth",
        details={"kinds": ["terms", "data_processing"], "version": body.terms_version},
    )
    return StatusOut(status="check_email")


@router.post(
    "/verify-email",
    dependencies=[Depends(require_csrf_header), Depends(rate_limit("verify", 20, 300))],
)
def verify_email(body: TokenIn, db: AuthDb) -> StatusOut:
    now = utcnow()
    tok = db.scalar(
        select(EmailToken).where(
            EmailToken.token_hash == security.token_digest(body.token),
            EmailToken.purpose == "verify_email",
        )
    )
    if tok is None or tok.used_at is not None or tok.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired token")
    tok.used_at = now
    user = db.get(User, tok.user_id)
    if user is not None and user.email_verified_at is None:
        user.email_verified_at = now
    return StatusOut(status="verified")


def _start_session(db: AuthDb, response: Response, user: User, *, mfa_verified: bool) -> str:
    settings = get_settings()
    token, csrf = security.new_token(), security.new_token()
    db.add(
        DbSession(
            user_id=user.id,
            token_hash=security.token_digest(token),
            csrf_token_hash=security.token_digest(csrf),
            mfa_verified=mfa_verified,
            expires_at=utcnow() + timedelta(hours=settings.session_absolute_hours),
        )
    )
    max_age = settings.session_absolute_hours * 3600
    response.set_cookie(
        session_cookie_name(),
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return csrf


@router.post(
    "/login", dependencies=[Depends(require_csrf_header), Depends(rate_limit("login", 10, 60))]
)
def login(body: LoginIn, response: Response, db: AuthDb) -> LoginOut:
    now = utcnow()
    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = security.verify_password(user.password_hash if user else None, body.password)
    generic = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    if user is None:
        raise generic
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status.HTTP_423_LOCKED, "account temporarily locked")
    if not password_ok or user.disabled_at is not None:
        user.failed_logins += 1
        if user.failed_logins >= LOCKOUT_THRESHOLD:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
        audit.record(
            db, action="auth.login_failed", org_id=None, actor_user_id=user.id, actor_kind="auth"
        )
        db.commit()  # persist the counter even though we fail the request
        raise generic
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")
    user.failed_logins = 0
    if user.password_hash and security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(body.password)
    csrf = _start_session(db, response, user, mfa_verified=False)
    audit.record(db, action="auth.login", org_id=None, actor_user_id=user.id, actor_kind="auth")
    db.flush()
    return LoginOut(
        csrf_token=csrf,
        mfa_required=user.mfa_enabled,
        mfa_enrollment_required=False,  # computed per org request; see /auth/me
    )


@router.post("/logout")
def logout(principal: CurrentPrincipal, response: Response) -> StatusOut:
    with tenant_session(None, principal.user_id) as db:
        db.execute(
            update(DbSession)
            .where(DbSession.id == principal.session_id)
            .values(revoked_at=utcnow())
        )
    response.delete_cookie(session_cookie_name(), path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return StatusOut(status="logged_out")


@router.post("/mfa/setup")
def mfa_setup(principal: CurrentPrincipal) -> MfaSetupOut:
    if principal.mfa_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA already enabled")
    secret = security.new_totp_secret()
    blob = get_envelope().encrypt_str(secret, f"users.totp_secret:{principal.user_id}")
    with tenant_session(None, principal.user_id) as db:
        db.execute(update(User).where(User.id == principal.user_id).values(totp_secret_enc=blob))
    return MfaSetupOut(otpauth_uri=security.totp_uri(secret, principal.email))


def _user_totp_secret(user: User) -> str | None:
    if user.totp_secret_enc is None:
        return None
    return get_envelope().decrypt_str(user.totp_secret_enc, f"users.totp_secret:{user.id}")


@router.post("/mfa/enable", dependencies=[Depends(rate_limit("mfa", 10, 300))])
def mfa_enable(body: CodeIn, principal: CurrentPrincipal) -> RecoveryCodesOut:
    with tenant_session(None, principal.user_id) as db:
        user = db.get(User, principal.user_id)
        assert user is not None
        secret = _user_totp_secret(user)
        if user.mfa_enabled or secret is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "run MFA setup first")
        if not body.code or not security.verify_totp(secret, body.code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
        codes = security.new_recovery_codes()
        user.mfa_enabled = True
        user.recovery_code_hashes = [security.recovery_code_digest(c) for c in codes]
        db.execute(
            update(DbSession).where(DbSession.id == principal.session_id).values(mfa_verified=True)
        )
        audit.record(db, action="auth.mfa_enabled", org_id=None, actor_user_id=principal.user_id)
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/mfa/verify", dependencies=[Depends(rate_limit("mfa", 10, 300))])
def mfa_verify(body: CodeIn, principal: CurrentPrincipal) -> StatusOut:
    # Per-account cap: the per-IP limit alone lets a distributed attacker brute-force TOTP.
    check_rate("mfa_user", str(principal.user_id), 10, 300)
    with tenant_session(None, principal.user_id) as db:
        user = db.get(User, principal.user_id)
        assert user is not None
        secret = _user_totp_secret(user)
        ok = False
        if user.mfa_enabled and secret and body.code:
            ok = security.verify_totp(secret, body.code)
        elif user.mfa_enabled and body.recovery_code:
            digest = security.recovery_code_digest(body.recovery_code)
            if digest in user.recovery_code_hashes:
                user.recovery_code_hashes = [h for h in user.recovery_code_hashes if h != digest]
                ok = True
        if not ok:
            audit.record(db, action="auth.mfa_failed", org_id=None, actor_user_id=principal.user_id)
            db.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid code")
        db.execute(
            update(DbSession).where(DbSession.id == principal.session_id).values(mfa_verified=True)
        )
    return StatusOut(status="mfa_verified")


@router.get("/me")
def me(principal: CurrentPrincipal) -> MeOut:
    with tenant_session(None, principal.user_id) as db:
        rows = db.execute(
            select(Membership.org_id, Organization.name, Organization.kind, Membership.role)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Organization.name)
        ).all()
    return MeOut(
        id=str(principal.user_id),
        email=principal.email,
        email_verified=principal.email_verified,
        mfa_enabled=principal.mfa_enabled,
        mfa_verified=principal.mfa_verified,
        mfa_required=user_requires_mfa(principal),
        is_platform_staff=principal.is_platform_staff,
        memberships=[
            MembershipOut(org_id=str(o), org_name=n, org_kind=k, role=r) for o, n, k, r in rows
        ],
    )

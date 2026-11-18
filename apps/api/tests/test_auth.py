from __future__ import annotations

import uuid
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient

from compback_core.config import get_settings

PASSWORD = "correct horse battery staple 42"


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


H = {"X-CSRF-Token": "x"}


def _signup(client: TestClient, email: str, **kw: object) -> int:
    body = {
        "email": email,
        "password": PASSWORD,
        "org_name": "Acme Roofing",
        "accept_terms": True,
        **kw,
    }
    return client.post("/auth/signup", json=body, headers=H).status_code


def test_full_signup_verify_login_flow(signup: Any) -> None:
    actor = signup()
    me = actor.client.get("/auth/me").json()
    assert me["email_verified"] is True
    assert me["memberships"][0]["role"] == "owner"
    assert me["mfa_required"] is False


def test_signup_requires_csrf_header(app_client: TestClient) -> None:
    r = app_client.post("/auth/signup", json={})
    assert r.status_code == 403


def test_signup_does_not_reveal_existing_email(app_client: TestClient) -> None:
    email = unique_email()
    assert _signup(app_client, email) == 202
    assert _signup(app_client, email) == 202  # same response for an existing account


@pytest.mark.parametrize("password", ["short", "aaaaaaaaaaaaaaaa"])
def test_weak_passwords_rejected(app_client: TestClient, password: str) -> None:
    r = app_client.post(
        "/auth/signup",
        headers=H,
        json={
            "email": unique_email(),
            "password": password,
            "org_name": "Acme",
            "accept_terms": True,
        },
    )
    assert r.status_code == 422


def test_terms_must_be_accepted(app_client: TestClient) -> None:
    assert _signup(app_client, unique_email(), accept_terms=False) == 422


def test_login_before_verification_is_refused(app_client: TestClient) -> None:
    email = unique_email()
    _signup(app_client, email)
    r = app_client.post("/auth/login", headers=H, json={"email": email, "password": PASSWORD})
    assert r.status_code == 403
    assert r.json()["detail"] == "email_not_verified"


def test_wrong_password_generic_error(app_client: TestClient) -> None:
    r = app_client.post(
        "/auth/login", headers=H, json={"email": unique_email(), "password": "nope-nope-nope"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid email or password"


def test_lockout_after_repeated_failures(signup: Any) -> None:
    actor = signup()
    c = TestClient(actor.client.app)
    for _ in range(10):
        c.post("/auth/login", headers=H, json={"email": actor.email, "password": "wrong-pw-xyz"})
    r = c.post("/auth/login", headers=H, json={"email": actor.email, "password": PASSWORD})
    assert r.status_code == 423


def test_verify_token_single_use(app_client: TestClient, email_token: Any) -> None:
    latest_email_token = email_token
    email = unique_email()
    _signup(app_client, email)
    token = latest_email_token(email)
    assert (
        app_client.post("/auth/verify-email", headers=H, json={"token": token}).status_code == 200
    )
    assert (
        app_client.post("/auth/verify-email", headers=H, json={"token": token}).status_code == 400
    )


def test_mutation_requires_matching_csrf(signup: Any) -> None:
    actor = signup()
    r = actor.client.post("/auth/mfa/setup", headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403
    r = actor.client.post("/auth/mfa/setup")
    assert r.status_code == 403


def test_session_cookie_flags(app_client: TestClient, email_token: Any) -> None:
    client = app_client
    latest_email_token = email_token
    email = unique_email()
    _signup(client, email)
    client.post("/auth/verify-email", headers=H, json={"token": latest_email_token(email)})
    r = client.post("/auth/login", headers=H, json={"email": email, "password": PASSWORD})
    cookie = next(v for k, v in r.headers.multi_items() if k == "set-cookie" and "cb_session" in v)
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie or "samesite=lax" in cookie.lower()


def test_logout_revokes_session(signup: Any) -> None:
    actor = signup()
    assert actor.post("/auth/logout").status_code == 200
    assert actor.client.get("/auth/me").status_code == 401


def test_mfa_enroll_then_login_requires_code(signup: Any, enroll: Any) -> None:
    actor = signup()
    codes = enroll(actor)
    assert len(codes) == 10
    c = TestClient(actor.client.app)
    r = c.post("/auth/login", headers=H, json={"email": actor.email, "password": PASSWORD})
    assert r.json()["mfa_required"] is True
    csrf = r.json()["csrf_token"]
    # org-scoped access blocked until MFA verified
    assert c.get(f"/orgs/{actor.org_id}").status_code == 403
    bad = c.post("/auth/mfa/verify", json={"code": "000000"}, headers={"X-CSRF-Token": csrf})
    assert bad.status_code == 400
    assert actor.totp_secret is not None
    ok = c.post(
        "/auth/mfa/verify",
        json={"code": pyotp.TOTP(actor.totp_secret).now()},
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 200
    assert c.get(f"/orgs/{actor.org_id}").status_code == 200


def test_recovery_code_is_single_use(signup: Any, enroll: Any) -> None:
    actor = signup()
    codes = enroll(actor)
    for expected in (200, 400):
        c = TestClient(actor.client.app)
        csrf = c.post(
            "/auth/login", headers=H, json={"email": actor.email, "password": PASSWORD}
        ).json()["csrf_token"]
        r = c.post(
            "/auth/mfa/verify", json={"recovery_code": codes[0]}, headers={"X-CSRF-Token": csrf}
        )
        assert r.status_code == expected


def test_rate_limit_login(monkeypatch: pytest.MonkeyPatch, app_client: TestClient) -> None:
    monkeypatch.setattr(get_settings(), "rate_limits_enabled", True)
    statuses = [
        app_client.post(
            "/auth/login", headers=H, json={"email": unique_email(), "password": "x" * 12}
        ).status_code
        for _ in range(25)
    ]
    assert 429 in statuses

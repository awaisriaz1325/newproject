"""API test fixtures. Tests run against a real PostgreSQL with migrations + RLS applied."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyotp
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from compback_api.main import create_app
from compback_core.db import tenant_session
from compback_core.models import EmailOutbox, User

ROOT = Path(__file__).resolve().parents[3]
PASSWORD = "correct horse battery staple 42"


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture
def app_client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def latest_email_token(email: str, template: str = "verify_email") -> str:
    with tenant_session(None, None, actor_kind="auth") as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        row = db.scalar(
            select(EmailOutbox)
            .where(EmailOutbox.to_user_id == user.id, EmailOutbox.template == template)
            .order_by(EmailOutbox.created_at.desc())
        )
        assert row is not None
        return str(row.payload["token"])


@dataclass
class Actor:
    client: TestClient
    email: str
    csrf: str
    org_id: str
    user_id: str
    totp_secret: str | None = None

    def post(self, url: str, json: object | None = None) -> Any:
        return self.client.post(url, json=json, headers={"X-CSRF-Token": self.csrf})

    def get(self, url: str) -> Any:
        return self.client.get(url)


def signup_and_login(org_kind: str = "employer", name: str | None = None) -> Actor:
    client = TestClient(create_app())
    email = unique_email(org_kind)
    r = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": PASSWORD,
            "org_name": name or f"Org {email}",
            "org_kind": org_kind,
            "accept_terms": True,
        },
        headers={"X-CSRF-Token": "x"},
    )
    assert r.status_code == 202, r.text
    token = latest_email_token(email)
    assert (
        client.post(
            "/auth/verify-email", json={"token": token}, headers={"X-CSRF-Token": "x"}
        ).status_code
        == 200
    )
    r = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}, headers={"X-CSRF-Token": "x"}
    )
    assert r.status_code == 200, r.text
    csrf = r.json()["csrf_token"]
    me = client.get("/auth/me").json()
    return Actor(
        client=client,
        email=email,
        csrf=csrf,
        org_id=me["memberships"][0]["org_id"],
        user_id=me["id"],
    )


def enroll_mfa(actor: Actor) -> list[str]:
    r = actor.client.post("/auth/mfa/setup", headers={"X-CSRF-Token": actor.csrf})
    assert r.status_code == 200, r.text
    secret = pyotp.parse_uri(r.json()["otpauth_uri"]).secret
    actor.totp_secret = secret
    r = actor.client.post(
        "/auth/mfa/enable",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-CSRF-Token": actor.csrf},
    )
    assert r.status_code == 200, r.text
    return list(r.json()["recovery_codes"])


def make_platform_staff(actor: Actor) -> None:
    with tenant_session(None, None, actor_kind="system") as db:
        db.execute(update(User).where(User.email == actor.email).values(is_platform_staff=True))


@pytest.fixture
def signup() -> object:
    return signup_and_login


@pytest.fixture
def enroll() -> object:
    return enroll_mfa


@pytest.fixture
def staff() -> object:
    return make_platform_staff


@pytest.fixture
def email_token() -> object:
    return latest_email_token

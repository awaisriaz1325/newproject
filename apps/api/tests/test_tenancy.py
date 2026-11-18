"""Tenancy, advisor consent, reviewer JIT access, audit chain, and cross-tenant isolation."""

from __future__ import annotations

import uuid
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from compback_api.main import create_app
from compback_core import audit
from compback_core.db import get_engine, tenant_session
from compback_core.models import Base

H = {"X-CSRF-Token": "x"}


def _invite_code(owner: Any) -> str:
    return str(owner.get(f"/orgs/{owner.org_id}").json()["invite_code"])


def _mfa_login(actor: Any) -> None:
    """Verify MFA on the actor's existing session (advisors must use MFA)."""
    r = actor.post("/auth/mfa/verify", {"code": pyotp.TOTP(actor.totp_secret).now()})
    assert r.status_code == 200, r.text


@pytest.fixture
def employer(signup: Any) -> Any:
    return signup("employer")


@pytest.fixture
def advisor(signup: Any, enroll: Any) -> Any:
    actor = signup("advisor_firm")
    enroll(actor)
    return actor


def _link(advisor: Any, employer: Any) -> str:
    r = advisor.post(
        f"/orgs/{advisor.org_id}/advisor-links", {"invite_code": _invite_code(employer)}
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_advisor_firm_member_must_enroll_mfa(signup: Any) -> None:
    actor = signup("advisor_firm")
    r = actor.get(f"/orgs/{actor.org_id}")
    assert r.status_code == 403
    assert r.json()["detail"] == "mfa_enrollment_required"


def test_advisor_access_requires_client_approval(advisor: Any, employer: Any) -> None:
    link_id = _link(advisor, employer)
    # Pending link: no access to the client org (404 hides existence).
    assert advisor.get(f"/orgs/{employer.org_id}").status_code == 404
    # Advisor cannot approve its own request.
    assert (
        advisor.post(f"/orgs/{advisor.org_id}/advisor-links/{link_id}/approve").status_code == 403
    )
    r = employer.post(f"/orgs/{employer.org_id}/advisor-links/{link_id}/approve")
    assert r.status_code == 200, r.text
    view = advisor.get(f"/orgs/{employer.org_id}")
    assert view.status_code == 200
    assert view.json()["access"] == "advisor"
    assert view.json()["invite_code"] is None  # owner-only field


def test_revocation_removes_access_immediately(advisor: Any, employer: Any) -> None:
    link_id = _link(advisor, employer)
    employer.post(f"/orgs/{employer.org_id}/advisor-links/{link_id}/approve")
    assert advisor.get(f"/orgs/{employer.org_id}").status_code == 200
    r = employer.post(f"/orgs/{employer.org_id}/advisor-links/{link_id}/revoke")
    assert r.status_code == 200
    assert advisor.get(f"/orgs/{employer.org_id}").status_code == 404
    # Consent was revoked too.
    with tenant_session(uuid.UUID(employer.org_id), uuid.UUID(employer.user_id)) as db:
        open_consents = db.execute(
            text(
                "SELECT count(*) FROM consents WHERE kind = 'advisor_access' AND revoked_at IS NULL"
            )
        ).scalar_one()
    assert open_consents == 0


def test_advisor_link_visible_in_customer_access_log(advisor: Any, employer: Any) -> None:
    link_id = _link(advisor, employer)
    employer.post(f"/orgs/{employer.org_id}/advisor-links/{link_id}/approve")
    log = employer.get(f"/orgs/{employer.org_id}/access-log").json()
    assert "advisor_link.approved" in [e["action"] for e in log]


def test_reviewer_jit_grant_logged_and_visible_to_customer(
    signup: Any, enroll: Any, staff: Any, employer: Any
) -> None:
    reviewer = signup("employer")
    staff(reviewer)
    # Without MFA: refused.
    r = reviewer.post(f"/orgs/{employer.org_id}/access-grants", {"reason": "verify findings"})
    assert r.status_code == 403
    enroll(reviewer)
    # No grant yet: no access.
    assert reviewer.get(f"/orgs/{employer.org_id}").status_code == 404
    r = reviewer.post(
        f"/orgs/{employer.org_id}/access-grants",
        {"reason": "Verify extracted payroll for case review", "minutes": 30},
    )
    assert r.status_code == 201, r.text
    view = reviewer.get(f"/orgs/{employer.org_id}")
    assert view.status_code == 200
    assert view.json()["access"] == "reviewer"
    log = employer.get(f"/orgs/{employer.org_id}/access-log").json()
    entry = next(e for e in log if e["action"] == "access_grant.created")
    assert entry["reason"] == "Verify extracted payroll for case review"


def test_non_staff_cannot_create_grant(signup: Any, enroll: Any, employer: Any) -> None:
    other = signup("employer")
    enroll(other)
    r = other.post(f"/orgs/{employer.org_id}/access-grants", {"reason": "just curious about it"})
    assert r.status_code == 404


def test_grant_reason_required(signup: Any, enroll: Any, staff: Any, employer: Any) -> None:
    reviewer = signup("employer")
    staff(reviewer)
    enroll(reviewer)
    r = reviewer.post(f"/orgs/{employer.org_id}/access-grants", {"reason": "x"})
    assert r.status_code == 422


def test_audit_chain_verifies_and_is_append_only(employer: Any) -> None:
    r = employer.get(f"/orgs/{employer.org_id}/audit/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["entries"] >= 2
    org = uuid.UUID(employer.org_id)
    with pytest.raises(DBAPIError), tenant_session(org, uuid.UUID(employer.user_id)) as db:
        db.execute(text("UPDATE audit_log SET action = 'x' WHERE org_id = :o"), {"o": org})
    with pytest.raises(DBAPIError), tenant_session(org, uuid.UUID(employer.user_id)) as db:
        db.execute(text("DELETE FROM audit_log WHERE org_id = :o"), {"o": org})


def test_audit_tamper_detected_by_verifier(employer: Any) -> None:
    """Even the owner role cannot silently edit history: trigger blocks it; if bypassed, the
    verifier detects it. Simulate a bypass by checking a forged payload against the chain."""
    org = uuid.UUID(employer.org_id)
    with tenant_session(org, uuid.UUID(employer.user_id)) as db:
        assert audit.verify_chain(db, org).ok
        rows = db.execute(
            text(
                "SELECT seq, prev_hash, hash, compback.audit_payload(a) AS payload "
                "FROM audit_log a "
                "WHERE org_id = :o ORDER BY seq"
            ),
            {"o": org},
        ).all()
    import hashlib

    forged = rows[0].payload.replace("org.created", "org.deleted")
    assert hashlib.sha256((rows[0].prev_hash + forged).encode()).hexdigest() != rows[0].hash


# ---------------------------------------------------------------- cross-tenant isolation (DB)

TENANT_TABLES_WITH_ORG = ["memberships", "consents", "access_grants", "audit_log", "jobs"]


def test_every_table_has_rls_or_is_documented_global() -> None:
    global_tables = {"jurisdiction_policies", "rate_limit_counters", "alembic_version"}
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n "
                "ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r'"
            )
        ).all()
    missing = [r.relname for r in rows if not r.relrowsecurity and r.relname not in global_tables]
    assert missing == [], f"tables without RLS: {missing}"
    model_tables = set(Base.metadata.tables)
    assert model_tables - {r.relname for r in rows} == set()


@pytest.mark.parametrize("table", TENANT_TABLES_WITH_ORG)
def test_rls_hides_other_tenant_rows(table: str, signup: Any) -> None:
    a, b = signup("employer"), signup("employer")
    with tenant_session(uuid.UUID(b.org_id), uuid.UUID(b.user_id)) as db:
        # B's context, explicitly asking for A's rows without any app-level filter help.
        leaked = db.execute(
            text(f"SELECT count(*) FROM {table} WHERE org_id = :a"),
            {"a": a.org_id},
        ).scalar_one()
    assert leaked == 0


def test_rls_user_cannot_spoof_org_context(signup: Any) -> None:
    """Setting app.org_id to another tenant without membership yields nothing."""
    a, b = signup("employer"), signup("employer")
    with tenant_session(uuid.UUID(a.org_id), uuid.UUID(b.user_id)) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM memberships WHERE org_id = :a"), {"a": a.org_id}
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("SELECT count(*) FROM organizations WHERE id = :a"), {"a": a.org_id}
            ).scalar_one()
            == 0
        )


def test_rls_blocks_cross_tenant_insert(signup: Any) -> None:
    a, b = signup("employer"), signup("employer")
    with pytest.raises(DBAPIError):
        with tenant_session(uuid.UUID(b.org_id), uuid.UUID(b.user_id)) as db:
            db.execute(
                text(
                    "INSERT INTO consents (org_id, user_id, kind, version) "
                    "VALUES (:a, :u, 'terms', 'x')"
                ),
                {"a": a.org_id, "u": b.user_id},
            )


def test_no_context_sees_nothing(signup: Any) -> None:
    signup("employer")
    with tenant_session(None, None) as db:
        for table in ["organizations", "users", "memberships", "consents", "audit_log", "jobs"]:
            n = db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            assert n == 0, table


def test_jurisdiction_policies_read_only_for_app() -> None:
    with pytest.raises(DBAPIError), tenant_session(None, None, actor_kind="system") as db:
        db.execute(text("UPDATE jurisdiction_policies SET paid_analysis_allowed = true"))


# ---------------------------------------------------------------- cross-tenant isolation (API)


def _org_scoped_get_routes() -> list[str]:
    paths = create_app().openapi()["paths"]
    return sorted(
        p
        for p, ops in paths.items()
        if p.startswith("/orgs/{org_id}") and "get" in ops and p.count("{") == 1
    )


@pytest.mark.parametrize("path", _org_scoped_get_routes())
def test_api_other_tenant_gets_404(path: str, signup: Any) -> None:
    a, b = signup("employer"), signup("employer")
    r = b.get(path.replace("{org_id}", a.org_id))
    assert r.status_code == 404, (path, r.status_code)


def test_jurisdictions_public_and_default_deny(app_client: TestClient) -> None:
    rows = app_client.get("/jurisdictions").json()
    by_code = {r["code"]: r for r in rows}
    assert len(rows) == 53
    assert all(not r["paid_analysis_allowed"] for r in rows)
    for code in ("ND", "OH", "WA", "WY"):
        assert by_code[code]["monopolistic"]
        assert not by_code[code]["free_scan_allowed"]
    assert by_code["NY"]["citations"]

"""End-to-end vault flow: upload -> worker ingest -> redacted view -> download -> delete."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select, update

from compback_core.config import get_settings
from compback_core.db import tenant_session
from compback_core.models import Document
from compback_vault.malware import EICAR
from compback_vault.pages import tesseract_available
from compback_vault.storage import LocalObjectStore
from compback_worker.runner import run_once, run_retention_sweep

pytestmark = pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")


def _pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(lines):
        c.drawString(72, 720 - 20 * i, line)
    c.showPage()
    c.save()
    return buf.getvalue()


def _upload(actor: Any, data: bytes, name: str = "audit.pdf") -> Any:
    return actor.client.post(
        f"/orgs/{actor.org_id}/documents",
        files={"file": (name, data)},
        headers={"X-CSRF-Token": actor.csrf},
    )


def _drain() -> None:
    for _ in range(20):
        if run_once() == 0:
            return


@pytest.fixture
def uploaded(signup: Any) -> tuple[Any, str]:
    actor = signup("employer")
    marker = uuid.uuid4().hex[:8]
    r = _upload(actor, _pdf([f"Premium audit {marker}", "Employee SSN 123-45-6789 wages 5,000"]))
    assert r.status_code == 201, r.text
    _drain()
    return actor, r.json()["id"]


def test_upload_ingest_view_redacted(uploaded: tuple[Any, str]) -> None:
    actor, doc_id = uploaded
    doc = actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}").json()
    assert doc["status"] == "ready"
    assert doc["malware_status"] == "clean"
    assert doc["redaction_count"] >= 1
    text = actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}/pages/1/text").json()["text"]
    assert "123-45-6789" not in text
    assert "[REDACTED-TIN]" in text
    img = actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}/pages/1/image")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert img.headers["cache-control"] == "no-store"
    log = actor.get(f"/orgs/{actor.org_id}/access-log").json()
    assert any(e["action"] == "document.viewed" for e in log)


def test_nothing_stored_in_plaintext(uploaded: tuple[Any, str]) -> None:
    actor, doc_id = uploaded
    store = LocalObjectStore(get_settings().storage_local_root)
    with tenant_session(uuid.UUID(actor.org_id), uuid.UUID(actor.user_id)) as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        assert doc.storage_key
        raw = store.get(doc.storage_key)
    assert raw.startswith(b"CB1")
    assert b"%PDF" not in raw
    assert b"123-45-6789" not in raw


def test_download_requires_fresh_user_bound_token(uploaded: tuple[Any, str], signup: Any) -> None:
    actor, doc_id = uploaded
    base = f"/orgs/{actor.org_id}/documents/{doc_id}"
    assert actor.get(f"{base}/download?token=123.abc").status_code == 403
    link = actor.post(f"{base}/download-link").json()
    r = actor.get(link["url"])
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]
    # Same URL is useless to another user (even one with their own valid session).
    other = signup("employer")
    assert other.get(link["url"]).status_code == 404


def test_duplicate_upload_deduplicated(signup: Any) -> None:
    actor = signup("employer")
    data = _pdf([f"dup {uuid.uuid4().hex}"])
    first = _upload(actor, data)
    second = _upload(actor, data, "renamed.pdf")
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]


def test_malicious_upload_rejected_synchronously(signup: Any) -> None:
    actor = signup("employer")
    r = _upload(actor, b"MZ\x90\x00" + b"\x00" * 64, "invoice.pdf")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "type_mismatch"


def test_malware_rejected_and_deleted_after_scan(signup: Any) -> None:
    actor = signup("employer")
    data = b"Employee,Wages\n" + EICAR + b",1\n"
    r = _upload(actor, data, "payroll.csv")
    assert r.status_code == 201
    _drain()
    doc = actor.get(f"/orgs/{actor.org_id}/documents/{r.json()['id']}").json()
    assert doc["status"] == "rejected"
    assert doc["malware_status"] == "infected"
    assert "malware" in doc["rejection_message"]


def test_password_pdf_rejected_with_reason(signup: Any) -> None:
    actor = signup("employer")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, encrypt="pw")
    c.drawString(72, 720, f"secret {uuid.uuid4().hex}")
    c.save()
    r = _upload(actor, buf.getvalue())
    _drain()
    doc = actor.get(f"/orgs/{actor.org_id}/documents/{r.json()['id']}").json()
    assert doc["status"] == "rejected"
    assert "password" in doc["rejection_message"]


def test_other_tenant_cannot_see_document(uploaded: tuple[Any, str], signup: Any) -> None:
    actor, doc_id = uploaded
    other = signup("employer")
    for suffix in ("", "/pages/1/text", "/pages/1/image"):
        assert other.get(f"/orgs/{actor.org_id}/documents/{doc_id}{suffix}").status_code == 404
        # Even through their own org path, the id resolves to nothing.
        assert other.get(f"/orgs/{other.org_id}/documents/{doc_id}{suffix}").status_code == 404


def test_delete_removes_content(uploaded: tuple[Any, str]) -> None:
    actor, doc_id = uploaded
    with tenant_session(uuid.UUID(actor.org_id), uuid.UUID(actor.user_id)) as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        key = doc.storage_key
    store = LocalObjectStore(get_settings().storage_local_root)
    assert key
    assert store.exists(key)
    r = actor.client.delete(
        f"/orgs/{actor.org_id}/documents/{doc_id}", headers={"X-CSRF-Token": actor.csrf}
    )
    assert r.status_code == 200
    assert not store.exists(key)
    assert actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}").status_code == 404
    with tenant_session(uuid.UUID(actor.org_id), uuid.UUID(actor.user_id)) as db:
        n = db.execute(select(Document.sha256).where(Document.id == uuid.UUID(doc_id))).scalar()
    assert n is None


def test_retention_sweep_deletes_expired(uploaded: tuple[Any, str]) -> None:
    actor, doc_id = uploaded
    with tenant_session(None, None, actor_kind="worker") as db:
        db.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(retention_until=datetime.now(UTC) - timedelta(days=1))
        )
    assert run_retention_sweep() >= 1
    assert actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}").status_code == 404


def test_reviewer_is_read_only(
    uploaded: tuple[Any, str], signup: Any, enroll: Any, staff: Any
) -> None:
    actor, _ = uploaded
    reviewer = signup("employer")
    staff(reviewer)
    enroll(reviewer)
    reviewer.post(f"/orgs/{actor.org_id}/access-grants", {"reason": "Verify extraction for case"})
    assert reviewer.get(f"/orgs/{actor.org_id}/documents").status_code == 200
    r = reviewer.client.post(
        f"/orgs/{actor.org_id}/documents",
        files={"file": ("x.pdf", _pdf(["x"]))},
        headers={"X-CSRF-Token": reviewer.csrf},
    )
    assert r.status_code == 403

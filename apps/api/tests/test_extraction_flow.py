"""Upload a synthetic audit and walk it through classification, extraction and verification."""

from __future__ import annotations

from typing import Any

import pytest

from compback_extract.synthetic import generate_case, render_pdf
from compback_vault.pages import tesseract_available
from compback_worker.runner import run_once

pytestmark = pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")


def _drain() -> None:
    for _ in range(30):
        if run_once() == 0:
            return


def _upload_case(actor: Any, seed: int, errors: tuple[str, ...] = ()) -> str:
    case = generate_case(seed, errors)
    r = actor.client.post(
        f"/orgs/{actor.org_id}/documents",
        files={"file": ("audit.pdf", render_pdf(case))},
        headers={"X-CSRF-Token": actor.csrf},
    )
    assert r.status_code == 201, r.text
    _drain()
    return str(r.json()["id"])


def test_clean_audit_extracts_ready(signup: Any) -> None:
    actor = signup("employer")
    doc_id = _upload_case(actor, 101)
    doc = actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}").json()
    assert doc["doc_type"] in ("premium_audit", "audit_billing")
    ext = actor.get(f"/orgs/{actor.org_id}/documents/{doc_id}/extraction").json()
    assert ext["issues"] == []
    assert ext["extractor"] == "heuristic-v1"
    assert len(ext["data"]["class_lines"]) >= 2


def test_arithmetic_error_needs_review_then_edit_and_verify(signup: Any) -> None:
    actor = signup("employer")
    doc_id = _upload_case(actor, 202, ("line_arithmetic",))
    base = f"/orgs/{actor.org_id}/documents/{doc_id}/extraction"
    ext = actor.get(base).json()
    assert ext["status"] == "needs_review"
    assert "arithmetic_inconsistency" in ext["review_reasons"]
    r = actor.client.patch(
        base,
        json={"edits": [{"path": "policy_number", "value": "WC-FIXED"}]},
        headers={"X-CSRF-Token": actor.csrf},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["policy_number"]["value"] == "WC-FIXED"
    bad = actor.client.patch(
        base,
        json={"edits": [{"path": "nonexistent", "value": "1"}]},
        headers={"X-CSRF-Token": actor.csrf},
    )
    assert bad.status_code == 422
    v = actor.post(f"{base}/verify")
    assert v.status_code == 200
    assert v.json()["status"] == "verified"
    log = actor.get(f"/orgs/{actor.org_id}/audit").json()
    assert {"extraction.edited", "extraction.verified"} <= {e["action"] for e in log}

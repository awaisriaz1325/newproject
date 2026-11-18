"""Upload -> extract -> verify -> analyze -> reviewer confirms, through the public API."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
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


def _setup(actor: Any, state: str, errors: tuple[str, ...], seed: int) -> tuple[str, Any]:
    case = generate_case(seed, errors, "statement")
    case.state = state
    case.lines = [replace(ln, state=state) for ln in case.lines]
    r = actor.client.post(
        f"/orgs/{actor.org_id}/documents",
        files={"file": ("audit.pdf", render_pdf(case))},
        headers={"X-CSRF-Token": actor.csrf},
    )
    doc_id = r.json()["id"]
    _drain()
    pol = actor.post(
        f"/orgs/{actor.org_id}/policies",
        {
            "carrier_name": case.carrier,
            "policy_number": case.policy_number,
            "state": state,
            "period_start": case.period_start.isoformat(),
            "period_end": case.period_end.isoformat(),
        },
    )
    assert pol.status_code == 201, pol.text
    pid = pol.json()["id"]
    assert actor.post(f"/orgs/{actor.org_id}/policies/{pid}/documents/{doc_id}").status_code == 200
    return pid, (case, doc_id)


def test_analysis_requires_verified_extraction_then_finds_error(
    signup: Any, enroll: Any, staff: Any
) -> None:
    actor = signup("employer")
    pid, (case, doc_id) = _setup(actor, "NC", ("line_arithmetic",), 11)
    base = f"/orgs/{actor.org_id}/policies/{pid}"
    blocked = actor.post(f"{base}/analyze")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "verification_required"
    actor.post(f"/orgs/{actor.org_id}/documents/{doc_id}/extraction/verify")
    r = actor.post(f"{base}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()
    finding = next(f for f in body["findings"] if f["detector"] == "line_arithmetic")
    assert finding["rule_id"] == "NC.3A1.LINE"
    assert finding["citations"][0]["section"] == "Rule 3-A-1"
    assert Decimal(finding["impact_high"]) == case.errors[0].overcharge
    assert Decimal(body["estimate_low"]) == case.errors[0].overcharge
    assert "not guaranteed" in body["estimate_label"]
    assert any(s["label"] == "Total premium" for s in body["steps"])
    assert finding["reviewer_status"] == "pending"

    # A platform reviewer with a JIT grant confirms the finding; the customer cannot.
    assert (
        actor.post(f"{base}/findings/{finding['id']}/review", {"status": "confirmed"}).status_code
        == 403
    )
    reviewer = signup("employer")
    staff(reviewer)
    enroll(reviewer)
    reviewer.post(
        f"/orgs/{actor.org_id}/access-grants", {"reason": "Review findings before customer report"}
    )
    ok = reviewer.post(
        f"{base}/findings/{finding['id']}/review",
        {"status": "confirmed", "note": "Arithmetic verified on page 1"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["reviewer_status"] == "confirmed"


def test_candidate_findings_hidden_from_customer(signup: Any, enroll: Any, staff: Any) -> None:
    actor = signup("employer")
    pid, (_, doc_id) = _setup(actor, "FL", ("line_arithmetic",), 12)
    actor.post(f"/orgs/{actor.org_id}/documents/{doc_id}/extraction/verify")
    base = f"/orgs/{actor.org_id}/policies/{pid}"
    body = actor.post(f"{base}/analyze").json()
    assert all(f["customer_visible"] for f in body["findings"])
    assert not any(f["detector"] == "line_arithmetic" for f in body["findings"])
    reviewer = signup("employer")
    staff(reviewer)
    enroll(reviewer)
    reviewer.post(f"/orgs/{actor.org_id}/access-grants", {"reason": "Expert review of candidates"})
    internal = reviewer.get(f"{base}/analysis").json()
    cand = next(f for f in internal["findings"] if f["detector"] == "line_arithmetic")
    assert cand["rule_status"] == "candidate"
    assert cand["reviewer_status"] == "needs_expert"
    r = reviewer.post(f"{base}/findings/{cand['id']}/review", {"status": "confirmed"})
    assert r.status_code == 409


def test_clean_audit_has_no_findings(signup: Any) -> None:
    actor = signup("employer")
    pid, (case, doc_id) = _setup(actor, "NC", (), 13)
    actor.post(f"/orgs/{actor.org_id}/documents/{doc_id}/extraction/verify")
    body = actor.post(f"/orgs/{actor.org_id}/policies/{pid}/analyze").json()
    assert body["findings"] == []
    assert Decimal(body["billed_total"]) == case.total_premium
    assert Decimal(body["estimate_high"]) == 0


@pytest.mark.parametrize("state", ["OH", "WA", "ND", "WY"])
def test_monopolistic_states_declined(signup: Any, state: str) -> None:
    actor = signup("employer")
    r = actor.post(
        f"/orgs/{actor.org_id}/policies",
        {
            "carrier_name": "State Fund",
            "policy_number": "X1",
            "state": state,
            "period_start": "2025-01-01",
            "period_end": "2026-01-01",
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "jurisdiction_not_supported"

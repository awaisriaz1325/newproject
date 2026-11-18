"""Full case lifecycle, from analysis to webhook."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from compback_core.config import get_settings
from compback_extract.synthetic import generate_case, render_pdf
from compback_vault.pages import tesseract_available
from compback_worker.runner import run_once

pytestmark = pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")


@pytest.fixture
def nc_paid_enabled() -> Any:
    owner = create_engine(get_settings().database_owner_url.get_secret_value())
    with owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE jurisdiction_policies SET paid_analysis_allowed = true, "
                "contingency_allowed = true WHERE code = 'NC'"
            )
        )
    yield
    with owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE jurisdiction_policies SET paid_analysis_allowed = false, "
                "contingency_allowed = false WHERE code = 'NC'"
            )
        )
    owner.dispose()


def _drain() -> None:
    for _ in range(30):
        if run_once() == 0:
            return


def _analyzed(actor: Any, state: str) -> tuple[str, Any]:
    case = generate_case(31, ("line_arithmetic",), "statement")
    case.state = state
    case.lines = [replace(ln, state=state) for ln in case.lines]
    doc = actor.client.post(
        f"/orgs/{actor.org_id}/documents",
        files={"file": ("audit.pdf", render_pdf(case))},
        headers={"X-CSRF-Token": actor.csrf},
    ).json()["id"]
    _drain()
    pid = actor.post(
        f"/orgs/{actor.org_id}/policies",
        {
            "carrier_name": case.carrier,
            "policy_number": case.policy_number,
            "state": state,
            "period_start": case.period_start.isoformat(),
            "period_end": case.period_end.isoformat(),
        },
    ).json()["id"]
    actor.post(f"/orgs/{actor.org_id}/policies/{pid}/documents/{doc}")
    actor.post(f"/orgs/{actor.org_id}/documents/{doc}/extraction/verify")
    assert actor.post(f"/orgs/{actor.org_id}/policies/{pid}/analyze").status_code == 201
    return pid, case


def _reviewer(signup: Any, enroll: Any, staff: Any, org_id: str) -> Any:
    reviewer = signup("employer")
    staff(reviewer)
    enroll(reviewer)
    reviewer.post(f"/orgs/{org_id}/access-grants", {"reason": "Case review and verification"})
    return reviewer


def test_paid_features_blocked_until_state_cleared(signup: Any) -> None:
    actor = signup("employer")
    pid, _ = _analyzed(actor, "FL")
    r = actor.post(f"/orgs/{actor.org_id}/cases", {"policy_id": pid})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "not_available_in_state"


def test_full_case_lifecycle(signup: Any, enroll: Any, staff: Any, nc_paid_enabled: Any) -> None:
    actor = signup("employer")
    pid, case = _analyzed(actor, "NC")
    org = actor.org_id
    reviewer = _reviewer(signup, enroll, staff, org)
    analysis = reviewer.get(f"/orgs/{org}/policies/{pid}/analysis").json()
    fid = next(f["id"] for f in analysis["findings"] if f["detector"] == "line_arithmetic")

    c = actor.post(f"/orgs/{org}/cases", {"policy_id": pid}).json()
    base = f"/orgs/{org}/cases/{c['id']}"
    assert c["deadline"].startswith("Unknown")
    assert actor.post(f"{base}/package").status_code == 409  # nothing confirmed yet
    reviewer.post(f"/orgs/{org}/policies/{pid}/findings/{fid}/review", {"status": "confirmed"})
    pkg = actor.post(f"{base}/package")
    assert pkg.status_code == 201, pkg.text
    assert pkg.json()["status"] == "ready_for_review"
    assert Decimal(pkg.json()["packages"][0]["total_high"]) == case.errors[0].overcharge
    pdf = actor.get(f"{base}/package/1.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert any("Contingency" in line for line in pkg.json()["fee_preview"])

    # Deadline only with a source.
    bad = actor.post(f"{base}/deadline", {"deadline_date": "2027-01-31", "source": "x"})
    assert bad.status_code == 422
    ok = actor.post(
        f"{base}/deadline",
        {"deadline_date": "2027-01-31", "source": "Carrier audit notice dated 2026-11-01"},
    )
    assert ok.json()["deadline"] == "2027-01-31"

    # Cannot skip ahead; owner approves; customer records their own submission.
    assert (
        actor.post(
            f"{base}/submitted", {"method": "email", "submitted_on": "2026-11-20"}
        ).status_code
        == 409
    )
    assert actor.post(f"{base}/approve").json()["status"] == "approved_by_customer"
    assert actor.post(f"{base}/fees/analysis").status_code == 201
    sub = actor.post(f"{base}/submitted", {"method": "email", "submitted_on": "2026-11-20"})
    assert sub.json()["status"] == "submitted"
    assert (
        actor.post(
            f"{base}/carrier-response", {"note": "Carrier agreed to correct line"}
        ).status_code
        == 200
    )

    # Outcome needs proof; reviewer verifies before any contingency fee.
    assert actor.post(f"{base}/outcomes", {"kind": "refund", "amount": "500.00"}).status_code == 422
    proof = actor.client.post(
        f"/orgs/{org}/documents",
        files={"file": ("refund.csv", b"Refund,Amount\nCheck,500.00\n")},
        headers={"X-CSRF-Token": actor.csrf},
    ).json()["id"]
    out = actor.post(
        f"{base}/outcomes", {"kind": "refund", "amount": "500.00", "proof_document_id": proof}
    ).json()
    assert out["status"] == "resolved"
    oid = out["outcomes"][0]["id"]
    assert actor.post(f"{base}/fees/contingency").status_code == 409  # not verified yet
    assert actor.post(f"{base}/outcomes/{oid}/verify").status_code == 403
    assert reviewer.post(f"{base}/outcomes/{oid}/verify").status_code == 200
    inv = actor.post(f"{base}/fees/contingency")
    assert inv.status_code == 201, inv.text
    fees = {f["kind"]: f for f in inv.json()["fees"]}
    # 25% of 500 = 125. Only *paid* analysis fees are credited; it is still unpaid here.
    assert Decimal(fees["contingency"]["amount"]) == Decimal("125.00")
    assert inv.json()["status"] == "fee_invoiced"

    # Stripe-style webhook: signature checked, idempotent.
    invoice_id = f"in_fake_{fees['contingency']['id']}"
    payload = json.dumps(
        {"id": "evt_1", "type": "invoice.paid", "data": {"object": {"id": invoice_id}}}
    )
    hook = actor.client.post(
        "/billing/stripe/webhook", content=payload, headers={"Stripe-Signature": "whsec_test"}
    )
    assert hook.json() == {"status": "ok"}
    again = actor.client.post(
        "/billing/stripe/webhook", content=payload, headers={"Stripe-Signature": "whsec_test"}
    )
    assert again.json() == {"status": "duplicate"}
    forged = actor.client.post(
        "/billing/stripe/webhook",
        content=payload.replace("evt_1", "x"),
        headers={"Stripe-Signature": "nope"},
    )
    assert forged.status_code == 400
    final = actor.get(base).json()
    assert {f["kind"]: f["status"] for f in final["fees"]}["contingency"] == "paid"
    assert [e["to"] for e in final["events"] if e["kind"] == "transition"] == [
        "ready_for_review",
        "approved_by_customer",
        "submitted",
        "carrier_responded",
        "resolved",
        "fee_invoiced",
    ]

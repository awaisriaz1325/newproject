from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from compback_disputes.package import (
    PackageInput,
    PackageItem,
    PackageValidationError,
    render_docx,
    render_pdf,
)
from compback_disputes.workflow import (
    TRANSITIONS,
    InvalidTransitionError,
    check_transition,
    contingency_fee,
)


def _inp(items: list[PackageItem]) -> PackageInput:
    return PackageInput(
        "Ridgeline Roofing LLC (Fictional)",
        "Example Mutual (Fictional)",
        "WC-123-SYN",
        "01/01/2025 - 01/01/2026",
        date(2026, 11, 18),
        items,
    )


ITEM = PackageItem(
    "f1",
    "Experience mod differs from the rating worksheet",
    "The bill applies 1.12; the worksheet shows 0.95.",
    Decimal("4210.55"),
    Decimal("4210.55"),
    "document 1a2b3c4d, page 1",
    "Consistency",
)


def test_pdf_and_docx_render_with_numbers_from_findings() -> None:
    pdf = render_pdf(_inp([ITEM]))
    assert pdf.startswith(b"%PDF")
    docx = render_docx(_inp([ITEM]))
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        xml = z.read("word/document.xml").decode()
    assert "$4,210.55" in xml
    assert "ATTORNEY REVIEW REQUIRED" in xml


def test_package_requires_findings_and_citations() -> None:
    with pytest.raises(PackageValidationError):
        render_pdf(_inp([]))
    bad = PackageItem("f2", "t", "e", Decimal(5), Decimal(1), "ev", "cite")
    with pytest.raises(PackageValidationError):
        render_pdf(_inp([bad]))
    no_cite = PackageItem("f3", "t", "e", Decimal(1), Decimal(1), "ev", " ")
    with pytest.raises(PackageValidationError):
        render_docx(_inp([no_cite]))


@pytest.mark.parametrize(
    ("recovery", "paid", "expected"),
    [
        (Decimal("10000"), Decimal("499"), Decimal("2001.00")),
        (Decimal("200000"), Decimal("499"), Decimal("24501.00")),  # capped at 25,000
        (Decimal("1000"), Decimal("499"), Decimal("0.00")),  # credit can't go below zero
        (Decimal("0"), Decimal("0"), Decimal("0.00")),
    ],
)
def test_contingency_fee(recovery: Decimal, paid: Decimal, expected: Decimal) -> None:
    q = contingency_fee(recovery, Decimal("0.25"), Decimal("25000"), paid, True)
    assert q.amount == expected
    assert q.lines[-1].endswith(f"${expected:,.2f}")


def test_state_machine() -> None:
    check_transition("draft", "ready_for_review")
    with pytest.raises(InvalidTransitionError):
        check_transition("draft", "submitted")
    assert TRANSITIONS["closed"] == frozenset()

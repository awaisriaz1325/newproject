"""Arithmetic cross-checks on extracted data.

Inconsistencies are *flagged*, never silently fixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from compback_extract.schemas import PremiumAuditV1, to_decimal

HUNDRED = Decimal(100)
# Carriers round line premiums to cents or whole dollars; allow half a dollar per line.
LINE_TOLERANCE = Decimal("0.50")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    field: str
    page: int | None
    expected: str | None = None
    found: str | None = None


def check_premium_audit(doc: PremiumAuditV1) -> list[Issue]:
    issues: list[Issue] = []
    line_sum = Decimal(0)
    lines_complete = True
    for i, line in enumerate(doc.class_lines):
        payroll, rate, premium = (
            to_decimal(line.payroll),
            to_decimal(line.rate),
            to_decimal(line.premium),
        )
        if None in (payroll, rate, premium):
            lines_complete = False
            issues.append(
                Issue(
                    "line_incomplete",
                    f"Class {line.class_code}: payroll, rate or premium missing or unreadable",
                    f"class_lines[{i}]",
                    line.page,
                )
            )
            continue
        assert payroll is not None
        assert rate is not None
        assert premium is not None
        expected = payroll / HUNDRED * rate
        if abs(expected - premium) > LINE_TOLERANCE:
            issues.append(
                Issue(
                    "line_arithmetic",
                    f"Class {line.class_code}: payroll x rate / 100 does not equal "
                    "the line premium",
                    f"class_lines[{i}].premium",
                    line.page,
                    expected=str(expected.quantize(Decimal("0.01"))),
                    found=str(premium),
                )
            )
        line_sum += premium
    total_manual = to_decimal(doc.total_manual_premium.value)
    if lines_complete and doc.class_lines and total_manual is not None:
        tolerance = LINE_TOLERANCE * len(doc.class_lines)
        if abs(line_sum - total_manual) > tolerance:
            issues.append(
                Issue(
                    "manual_total",
                    "Sum of class premiums does not equal the stated manual premium",
                    "total_manual_premium",
                    doc.total_manual_premium.page,
                    expected=str(line_sum),
                    found=str(total_manual),
                )
            )
    billed, total, balance = (
        to_decimal(doc.previously_billed.value),
        to_decimal(doc.total_premium.value),
        to_decimal(doc.balance.value),
    )
    if None not in (billed, total, balance):
        assert billed is not None
        assert total is not None
        assert balance is not None
        if abs((total - billed) - balance) > Decimal("1.00"):
            issues.append(
                Issue(
                    "balance",
                    "Total premium minus previously billed does not equal the balance",
                    "balance",
                    doc.balance.page,
                    expected=str(total - billed),
                    found=str(balance),
                )
            )
    return issues

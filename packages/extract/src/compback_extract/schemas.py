"""Versioned extraction schemas.

LLM-facing schemas keep money as decimal *strings* (exact, JSON-schema friendly); conversion to
``Decimal`` happens in ``to_decimal`` with validation. Every scalar carries the page it came from
and a confidence in [0, 1]. Schema changes bump ``SCHEMA_VERSION`` and add a new class, never
mutate an old one (stored extractions reference the version they were produced with).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "2026-11-18.v1"
DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")

DocType = Literal[
    "policy_declarations",
    "premium_audit",
    "audit_billing",
    "experience_rating",
    "payroll_register",
    "payroll_tax_form",
    "certificate_of_insurance",
    "carrier_correspondence",
    "quote",
    "unknown",
]


class Fld(BaseModel):
    """One extracted scalar with provenance. ``value`` is None when not present on the page."""

    value: str | None = None
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ClassLine(BaseModel):
    state: str | None = Field(default=None, description="Two-letter US state code")
    class_code: str = Field(description="Workers comp class code as printed, e.g. 5645")
    description: str | None = None
    payroll: str | None = Field(default=None, description="Exposure/payroll, decimal string")
    rate: str | None = Field(default=None, description="Rate per $100 of payroll, decimal string")
    premium: str | None = Field(default=None, description="Line premium, decimal string")
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Charge(BaseModel):
    label: str
    amount: str = Field(description="Decimal string; negative for credits")
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PremiumAuditV1(BaseModel):
    """Premium audit statement / final audit billing."""

    carrier_name: Fld = Fld()
    policy_number: Fld = Fld()
    period_start: Fld = Fld()
    period_end: Fld = Fld()
    audit_type: Fld = Fld()
    class_lines: list[ClassLine] = Field(default_factory=list)
    total_manual_premium: Fld = Fld()
    experience_mod: Fld = Fld()
    schedule_mod: Fld = Fld()
    premium_discount: Fld = Fld()
    expense_constant: Fld = Fld()
    other_charges: list[Charge] = Field(default_factory=list)
    total_premium: Fld = Fld()
    previously_billed: Fld = Fld()
    balance: Fld = Fld()


class PolicyDeclarationsV1(BaseModel):
    carrier_name: Fld = Fld()
    policy_number: Fld = Fld()
    period_start: Fld = Fld()
    period_end: Fld = Fld()
    states: list[str] = Field(default_factory=list)
    class_lines: list[ClassLine] = Field(default_factory=list)
    experience_mod: Fld = Fld()
    schedule_mod: Fld = Fld()
    promised_credits: list[Charge] = Field(default_factory=list)
    expense_constant: Fld = Fld()
    estimated_premium: Fld = Fld()


class ExperienceRatingV1(BaseModel):
    state: Fld = Fld()
    rating_effective_date: Fld = Fld()
    experience_mod: Fld = Fld()


class PayrollSummaryV1(BaseModel):
    period_start: Fld = Fld()
    period_end: Fld = Fld()
    total_gross_wages: Fld = Fld()
    overtime_premium_pay: Fld = Fld()
    overtime_total_pay: Fld = Fld()
    overtime_basis: Fld = Fld()  # "premium_portion" | "time_and_a_half_total" | "double_time_total"
    officer_payroll: Fld = Fld()


class CertificateOfInsuranceV1(BaseModel):
    subcontractor_name: Fld = Fld()
    wc_policy_number: Fld = Fld()
    carrier_name: Fld = Fld()
    effective_date: Fld = Fld()
    expiration_date: Fld = Fld()


SCHEMAS: dict[str, type[BaseModel]] = {
    "premium_audit": PremiumAuditV1,
    "audit_billing": PremiumAuditV1,
    "policy_declarations": PolicyDeclarationsV1,
    "quote": PolicyDeclarationsV1,
    "experience_rating": ExperienceRatingV1,
    "payroll_register": PayrollSummaryV1,
    "payroll_tax_form": PayrollSummaryV1,
    "certificate_of_insurance": CertificateOfInsuranceV1,
}


def to_decimal(value: str | None) -> Decimal | None:
    """Parse an extracted decimal string. Commas/$ tolerated; anything else is rejected (None)."""
    if value is None:
        return None
    cleaned = value.replace(",", "").replace("$", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    if not DECIMAL_RE.match(cleaned):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None

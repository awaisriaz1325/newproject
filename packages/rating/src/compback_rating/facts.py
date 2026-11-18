"""Normalized, verified inputs to the engine (Decimal only). Built from verified extractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Evidence:
    document_id: str | None
    page: int | None
    field: str


@dataclass(frozen=True)
class AuditLine:
    state: str
    class_code: str
    description: str
    payroll: Decimal
    rate: Decimal
    printed_premium: Decimal | None
    evidence: Evidence


@dataclass(frozen=True)
class Charge:
    label: str
    amount: Decimal
    evidence: Evidence


@dataclass
class AuditFacts:
    state: str
    period_start: date | None
    period_end: date | None
    lines: list[AuditLine]
    experience_mod: Decimal | None
    schedule_amount: Decimal | None  # printed schedule credit/debit amount (credit negative)
    premium_discount: Decimal | None  # printed (negative)
    expense_constant: Decimal | None
    other_charges: list[Charge] = field(default_factory=list)
    printed_manual: Decimal | None = None
    printed_total: Decimal | None = None
    previously_billed: Decimal | None = None
    printed_balance: Decimal | None = None
    evidence: dict[str, Evidence] = field(default_factory=dict)


@dataclass(frozen=True)
class DeclarationFacts:
    schedule_credit_pct: Decimal | None  # 0.10 = 10% credit promised
    experience_mod: Decimal | None
    evidence: Evidence


@dataclass(frozen=True)
class WorksheetFacts:
    experience_mod: Decimal
    effective_date: date | None
    evidence: Evidence


@dataclass(frozen=True)
class PayrollFacts:
    total_gross_wages: Decimal
    overtime_premium_pay: Decimal | None
    evidence: Evidence


@dataclass(frozen=True)
class CoiFacts:
    subcontractor: str
    effective: date
    expiration: date
    evidence: Evidence


@dataclass
class AnalysisContext:
    audit: AuditFacts
    declarations: DeclarationFacts | None = None
    worksheets: list[WorksheetFacts] = field(default_factory=list)
    payroll: PayrollFacts | None = None
    cois: list[CoiFacts] = field(default_factory=list)

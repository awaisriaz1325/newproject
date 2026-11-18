"""Build engine inputs from stored (verified/ready) extractions. Unparseable values stay None."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from compback_extract.schemas import (
    ExperienceRatingV1,
    Fld,
    PayrollSummaryV1,
    PolicyDeclarationsV1,
    PremiumAuditV1,
    to_decimal,
)
from compback_rating.facts import (
    AnalysisContext,
    AuditFacts,
    AuditLine,
    Charge,
    DeclarationFacts,
    Evidence,
    PayrollFacts,
    WorksheetFacts,
)

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()  # noqa: DTZ007 - date only
        except ValueError:
            continue
    return None


def _ev(doc_id: str, fld: Fld, name: str) -> Evidence:
    return Evidence(doc_id, fld.page, name)


def audit_facts(doc_id: str, data: dict[str, Any], state: str) -> AuditFacts:
    a = PremiumAuditV1.model_validate(data)
    lines = []
    for i, ln in enumerate(a.class_lines):
        payroll, rate = to_decimal(ln.payroll), to_decimal(ln.rate)
        if payroll is None or rate is None:
            continue  # incomplete lines are surfaced by cross-checks, not guessed
        lines.append(
            AuditLine(
                ln.state or state,
                ln.class_code,
                ln.description or "",
                payroll,
                rate,
                to_decimal(ln.premium),
                Evidence(doc_id, ln.page, f"class_lines[{i}]"),
            )
        )
    schedule = to_decimal(a.schedule_mod.value)
    charges = []
    for i, ch in enumerate(a.other_charges):
        amount = to_decimal(ch.amount)
        if amount is None:
            continue
        if "schedule" in ch.label.lower():
            schedule = schedule if schedule is not None else amount
            continue
        charges.append(Charge(ch.label, amount, Evidence(doc_id, ch.page, f"other_charges[{i}]")))
    names = [
        "total_manual_premium",
        "experience_mod",
        "total_premium",
        "previously_billed",
        "balance",
        "expense_constant",
    ]
    return AuditFacts(
        state=state,
        period_start=parse_date(a.period_start.value),
        period_end=parse_date(a.period_end.value),
        lines=lines,
        experience_mod=to_decimal(a.experience_mod.value),
        schedule_amount=schedule,
        premium_discount=to_decimal(a.premium_discount.value),
        expense_constant=to_decimal(a.expense_constant.value),
        other_charges=charges,
        printed_manual=to_decimal(a.total_manual_premium.value),
        printed_total=to_decimal(a.total_premium.value),
        previously_billed=to_decimal(a.previously_billed.value),
        printed_balance=to_decimal(a.balance.value),
        evidence={n: _ev(doc_id, getattr(a, n), n) for n in names},
    )


def build_context(
    state: str, extractions: list[tuple[str, str, dict[str, Any]]]
) -> AnalysisContext | None:
    """``extractions``: (document_id, doc_type, data). Returns None without an audit."""
    audit = next(
        (
            audit_facts(d, data, state)
            for d, t, data in extractions
            if t in ("premium_audit", "audit_billing")
        ),
        None,
    )
    if audit is None:
        return None
    ctx = AnalysisContext(audit=audit)
    for doc_id, doc_type, data in extractions:
        if doc_type in ("policy_declarations", "quote") and ctx.declarations is None:
            d = PolicyDeclarationsV1.model_validate(data)
            pct = next(
                (
                    abs(v) / 100
                    for c in d.promised_credits
                    if "schedule" in c.label.lower() and (v := to_decimal(c.amount))
                ),
                None,
            )
            ctx.declarations = DeclarationFacts(
                pct, to_decimal(d.experience_mod.value), Evidence(doc_id, None, "promised_credits")
            )
        elif doc_type == "experience_rating":
            w = ExperienceRatingV1.model_validate(data)
            mod = to_decimal(w.experience_mod.value)
            if mod is not None:
                ctx.worksheets.append(
                    WorksheetFacts(
                        mod,
                        parse_date(w.rating_effective_date.value),
                        _ev(doc_id, w.experience_mod, "experience_mod"),
                    )
                )
        elif doc_type in ("payroll_register", "payroll_tax_form") and ctx.payroll is None:
            p = PayrollSummaryV1.model_validate(data)
            gross = to_decimal(p.total_gross_wages.value)
            if gross is not None:
                ctx.payroll = PayrollFacts(
                    gross,
                    to_decimal(p.overtime_premium_pay.value),
                    _ev(doc_id, p.total_gross_wages, "total_gross_wages"),
                )
    return ctx


def zero_if_none(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal(0)

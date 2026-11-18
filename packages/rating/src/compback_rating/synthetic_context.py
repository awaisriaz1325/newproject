"""Build engine inputs straight from a synthetic case (golden tests and evaluation only)."""

from __future__ import annotations

from compback_extract.synthetic import SyntheticCase
from compback_rating.facts import (
    AnalysisContext,
    AuditFacts,
    AuditLine,
    DeclarationFacts,
    Evidence,
    PayrollFacts,
    WorksheetFacts,
)


def context_from_case(case: SyntheticCase) -> AnalysisContext:
    ev = Evidence(case.case_id, 1, "synthetic")
    audit = AuditFacts(
        state=case.state,
        period_start=case.period_start,
        period_end=case.period_end,
        lines=[
            AuditLine(
                ln.state,
                ln.code,
                ln.description,
                ln.payroll,
                ln.rate,
                case.line_premium(i),
                Evidence(case.case_id, 1, f"class_lines[{i}]"),
            )
            for i, ln in enumerate(case.lines)
        ],
        experience_mod=case.mod,
        schedule_amount=case.schedule_amount if case.schedule_credit_applied else None,
        premium_discount=None,
        expense_constant=case.expense_constant,
        printed_manual=case.manual_premium,
        printed_total=case.total_premium,
        previously_billed=case.previously_billed,
        printed_balance=case.balance,
    )
    return AnalysisContext(
        audit=audit,
        declarations=DeclarationFacts(case.schedule_credit_pct or None, case.worksheet_mod, ev),
        worksheets=[WorksheetFacts(case.worksheet_mod, case.period_start, ev)],
        payroll=PayrollFacts(case.payroll_records_total, case.overtime_premium_pay or None, ev),
    )

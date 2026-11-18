"""Deterministic Decimal premium recomputation with a line-by-line explanation (no LLM inside).

v1 uses the rates, factors, credits and constants printed on the customer's own documents and
recomputes the arithmetic in the order verified for NC (Rule 3-A) — which is also the order these
elements are printed on the bill elsewhere (UNVERIFIED per state; recorded on each step).

Rounding (ADR-0008): each line premium, the modified premium and the schedule amount are rounded to
cents with ROUND_HALF_UP; intermediate products keep full precision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal

from compback_rating.facts import AuditFacts, AuditLine
from compback_rating.rules import REGISTRY_VERSION, pick

ENGINE_VERSION = "1.0.0"
CENT = Decimal("0.01")
HUNDRED = Decimal(100)
ONE = Decimal(1)


def r2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Step:
    label: str
    formula: str
    result: Decimal
    rule_id: str | None = None


@dataclass(frozen=True)
class Overrides:
    """What-if corrections used to price a finding's impact."""

    experience_mod: Decimal | None = None
    schedule_credit_pct: Decimal | None = None  # recompute schedule as -modified x pct
    drop_line_indexes: frozenset[int] = frozenset()
    payroll_adjustments: tuple[tuple[int, Decimal], ...] = ()  # (line index, delta)
    use_printed_line_premiums: bool = False


@dataclass
class Recomputation:
    steps: list[Step] = field(default_factory=list)
    line_premiums: list[Decimal] = field(default_factory=list)
    manual: Decimal = Decimal(0)
    modified: Decimal = Decimal(0)
    schedule: Decimal = Decimal(0)
    standard: Decimal = Decimal(0)
    discount: Decimal = Decimal(0)
    expense_constant: Decimal = Decimal(0)
    other: Decimal = Decimal(0)
    total: Decimal = Decimal(0)
    engine_version: str = ENGINE_VERSION
    registry_version: str = REGISTRY_VERSION


def recompute(audit: AuditFacts, ov: Overrides | None = None) -> Recomputation:
    ov = ov or Overrides()
    out = Recomputation()
    line_rule = pick(audit.state, "NC.3A1.LINE", "NCCI.LINE").id
    order_rule = "NC.3A.ORDER" if audit.state == "NC" else None
    adjustments = dict(ov.payroll_adjustments)
    for i, line in enumerate(audit.lines):
        if i in ov.drop_line_indexes:
            out.line_premiums.append(Decimal(0))
            continue
        payroll = line.payroll + adjustments.get(i, Decimal(0))
        if (
            ov.use_printed_line_premiums
            and line.printed_premium is not None
            and i not in adjustments
        ):
            premium = line.printed_premium
            formula = f"as printed: {premium}"
        else:
            premium = r2(payroll / HUNDRED * line.rate)
            formula = f"{payroll} / 100 x {line.rate}"
        out.line_premiums.append(premium)
        out.steps.append(
            Step(f"Class {line.class_code} ({line.state})", formula, premium, line_rule)
        )
    out.manual = sum(out.line_premiums, Decimal(0))
    out.steps.append(Step("Manual premium", "sum of class premiums", out.manual, "CONS.TOTALS"))
    mod = ov.experience_mod if ov.experience_mod is not None else (audit.experience_mod or ONE)
    out.modified = r2(out.manual * mod)
    out.steps.append(
        Step("Experience modification", f"{out.manual} x {mod}", out.modified, order_rule)
    )
    if ov.schedule_credit_pct is not None:
        out.schedule = -r2(out.modified * ov.schedule_credit_pct)
        sched_formula = f"-({out.modified} x {ov.schedule_credit_pct})"
    else:
        out.schedule = audit.schedule_amount or Decimal(0)
        sched_formula = "as printed"
    out.steps.append(Step("Schedule rating", sched_formula, out.schedule, order_rule))
    out.standard = out.modified + out.schedule
    out.steps.append(Step("Standard premium", "modified + schedule", out.standard, order_rule))
    out.discount = audit.premium_discount or Decimal(0)
    out.steps.append(Step("Premium discount", "as printed", out.discount, order_rule))
    out.expense_constant = audit.expense_constant or Decimal(0)
    out.steps.append(
        Step(
            "Expense constant",
            "as printed (not subject to mod/discount)",
            out.expense_constant,
            order_rule,
        )
    )
    out.other = sum((c.amount for c in audit.other_charges), Decimal(0))
    if audit.other_charges:
        out.steps.append(
            Step("Other charges", " + ".join(c.label for c in audit.other_charges), out.other)
        )
    out.total = out.standard + out.discount + out.expense_constant + out.other
    out.steps.append(
        Step("Total premium", "standard + discount + constant + other", out.total, "CONS.TOTALS")
    )
    return out


def inputs_hash(audit: AuditFacts) -> str:
    """Stable hash of engine inputs (order-independent over lines)."""
    lines = sorted(
        (ln.state, ln.class_code, str(ln.payroll), str(ln.rate), str(ln.printed_premium))
        for ln in audit.lines
    )
    payload = {
        "state": audit.state,
        "lines": lines,
        "mod": str(audit.experience_mod),
        "schedule": str(audit.schedule_amount),
        "discount": str(audit.premium_discount),
        "constant": str(audit.expense_constant),
        "other": sorted((c.label, str(c.amount)) for c in audit.other_charges),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def with_lines(audit: AuditFacts, lines: list[AuditLine]) -> AuditFacts:
    return replace(audit, lines=lines)

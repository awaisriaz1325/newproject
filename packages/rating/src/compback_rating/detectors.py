"""v1 detectors (build prompt §5).

Each returns findings with rule, evidence, impact range and confidence.

Impact = premium as billed minus premium with the correction, priced by the engine (what-if), so
corrections flow through the experience mod and schedule rating exactly as the bill applies them.
Positive impact = the policyholder appears overcharged. Findings below MIN_IMPACT are dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from compback_rating.engine import Overrides, r2, recompute
from compback_rating.facts import AnalysisContext, Evidence
from compback_rating.rules import Rule, RuleStatus, pick, rule

MIN_IMPACT = Decimal("1.00")
PAYROLL_TOLERANCE = Decimal("0.01")  # 1% of records total
TOTAL_TOLERANCE = Decimal("1.00")


@dataclass
class Finding:
    detector: str
    rule: Rule
    title: str
    explanation: str
    impact_low: Decimal
    impact_high: Decimal
    confidence: Decimal
    evidence: list[Evidence] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    @property
    def customer_visible(self) -> bool:
        return self.rule.status == RuleStatus.ACTIVE


def _billed_total(ctx: AnalysisContext) -> Decimal:
    return recompute(ctx.audit, Overrides(use_printed_line_premiums=True)).total


def implied_schedule_pct(ctx: AnalysisContext) -> Decimal | None:
    """Schedule rating is a percentage of modified premium; keep it proportional in what-ifs."""
    if not ctx.audit.schedule_amount:
        return None
    if ctx.declarations and ctx.declarations.schedule_credit_pct:
        return ctx.declarations.schedule_credit_pct
    billed = recompute(ctx.audit, Overrides(use_printed_line_premiums=True))
    return -ctx.audit.schedule_amount / billed.modified if billed.modified else None


def _impact(ctx: AnalysisContext, corrected: Overrides) -> Decimal:
    values = {**corrected.__dict__, "use_printed_line_premiums": True}
    if values["schedule_credit_pct"] is None:
        values["schedule_credit_pct"] = implied_schedule_pct(ctx)
    return _billed_total(ctx) - recompute(ctx.audit, Overrides(**values)).total


def detect_line_arithmetic(ctx: AnalysisContext) -> list[Finding]:
    out = []
    the_rule = pick(ctx.audit.state, "NC.3A1.LINE", "NCCI.LINE")
    for i, line in enumerate(ctx.audit.lines):
        if line.printed_premium is None:
            continue
        expected = r2(line.payroll / 100 * line.rate)
        if abs(line.printed_premium - expected) <= Decimal("0.50"):
            continue
        impact = _impact(ctx, Overrides(payroll_adjustments=((i, Decimal(0)),)))
        out.append(
            Finding(
                "line_arithmetic",
                the_rule,
                f"Class {line.class_code} premium does not match payroll x rate",
                f"Printed premium {line.printed_premium} but {line.payroll} / 100 x {line.rate} = "
                f"{expected}.",
                impact,
                impact,
                Decimal("0.95"),
                [line.evidence],
            )
        )
    return out


def detect_total_arithmetic(ctx: AnalysisContext) -> list[Finding]:
    audit = ctx.audit
    out = []
    billed = recompute(audit, Overrides(use_printed_line_premiums=True))
    if (
        audit.printed_manual is not None
        and abs(audit.printed_manual - billed.manual) > TOTAL_TOLERANCE
    ):
        delta = audit.printed_manual - billed.manual
        out.append(
            Finding(
                "manual_total",
                rule("CONS.TOTALS"),
                "Manual premium total does not add up",
                f"Printed manual premium {audit.printed_manual}; sum of printed class premiums "
                f"{billed.manual}.",
                r2(delta * (audit.experience_mod or 1)),
                r2(delta * (audit.experience_mod or 1)),
                Decimal("0.9"),
                [e for k, e in audit.evidence.items() if k == "total_manual_premium"],
            )
        )
    if (
        audit.printed_total is not None
        and abs(audit.printed_total - billed.total) > TOTAL_TOLERANCE
        and not out
    ):
        delta = audit.printed_total - billed.total
        out.append(
            Finding(
                "total_premium",
                rule("CONS.TOTALS"),
                "Total premium does not add up",
                f"Printed total {audit.printed_total}; printed components add to {billed.total}.",
                delta,
                delta,
                Decimal("0.85"),
                [e for k, e in audit.evidence.items() if k == "total_premium"],
            )
        )
    return out


def detect_mod_mismatch(ctx: AnalysisContext) -> list[Finding]:
    if not ctx.worksheets or ctx.audit.experience_mod is None:
        return []
    ws = ctx.worksheets[0]
    if ws.experience_mod == ctx.audit.experience_mod:
        return []
    impact = _impact(ctx, Overrides(experience_mod=ws.experience_mod))
    return [
        Finding(
            "mod_mismatch",
            rule("CONS.MOD"),
            "Experience mod differs from the rating worksheet",
            f"The bill applies {ctx.audit.experience_mod}; the experience rating worksheet shows "
            f"{ws.experience_mod}.",
            impact,
            impact,
            Decimal("0.85"),
            [ctx.audit.evidence.get("experience_mod", ws.evidence), ws.evidence],
            ["Worksheet effective date matches this policy period"],
        )
    ]


def detect_missing_credit(ctx: AnalysisContext) -> list[Finding]:
    dec = ctx.declarations
    if dec is None or not dec.schedule_credit_pct or ctx.audit.schedule_amount:
        return []
    impact = _impact(ctx, Overrides(schedule_credit_pct=dec.schedule_credit_pct))
    return [
        Finding(
            "missing_credit",
            rule("CONS.CREDIT"),
            "Promised schedule credit missing from final bill",
            f"The policy shows a {dec.schedule_credit_pct * 100:.0f}% schedule credit; the final "
            "bill applies none.",
            impact,
            impact,
            Decimal("0.8"),
            [dec.evidence],
            ["Credit was not withdrawn mid-term by endorsement"],
        )
    ]


def detect_duplicates(ctx: AnalysisContext) -> list[Finding]:
    seen: dict[tuple[str, str, Decimal], int] = {}
    out = []
    for i, line in enumerate(ctx.audit.lines):
        key = (line.state, line.class_code, line.payroll)
        if key in seen:
            impact = _impact(ctx, Overrides(drop_line_indexes=frozenset({i})))
            out.append(
                Finding(
                    "duplicate_class",
                    rule("CONS.DUPLICATE"),
                    f"Class {line.class_code} payroll appears twice",
                    f"Two lines charge class {line.class_code} on identical payroll "
                    f"{line.payroll}.",
                    Decimal(0),
                    impact,
                    Decimal("0.5"),
                    [ctx.audit.lines[seen[key]].evidence, line.evidence],
                    ["The lines are not separate locations or separate periods"],
                )
            )
        else:
            seen[key] = i
    return out


def _spread(ctx: AnalysisContext, excess: Decimal) -> tuple[Decimal, Decimal]:
    """Impact of removing ``excess`` payroll, attributed to the cheapest vs dearest class."""
    if not ctx.audit.lines:
        return Decimal(0), Decimal(0)
    idx = sorted(range(len(ctx.audit.lines)), key=lambda k: ctx.audit.lines[k].rate)
    low_i, high_i = idx[0], idx[-1]
    low = _impact(ctx, Overrides(payroll_adjustments=((low_i, -excess),)))
    high = _impact(ctx, Overrides(payroll_adjustments=((high_i, -excess),)))
    return min(low, high), max(low, high)


def _audited_net_of_duplicates(ctx: AnalysisContext) -> Decimal:
    """Audited payroll excluding lines already flagged as duplicates (avoid double counting)."""
    seen: set[tuple[str, str, Decimal]] = set()
    total = Decimal(0)
    for ln in ctx.audit.lines:
        key = (ln.state, ln.class_code, ln.payroll)
        if key not in seen:
            total += ln.payroll
            seen.add(key)
    return total


def detect_payroll_mismatch(ctx: AnalysisContext) -> list[Finding]:
    if ctx.payroll is None:
        return []
    audited = _audited_net_of_duplicates(ctx)
    excess = audited - ctx.payroll.total_gross_wages
    if excess <= ctx.payroll.total_gross_wages * PAYROLL_TOLERANCE:
        return []
    low, high = _spread(ctx, excess)
    return [
        Finding(
            "payroll_mismatch",
            rule("CONS.PAYROLL"),
            "Audited payroll exceeds payroll records",
            f"Audited payroll {audited} exceeds total gross wages in payroll records "
            f"{ctx.payroll.total_gross_wages} by {excess}.",
            low,
            high,
            Decimal("0.7"),
            [ctx.payroll.evidence],
            ["Payroll records cover the same period and entity"],
        )
    ]


def detect_overtime(ctx: AnalysisContext) -> list[Finding]:
    p = ctx.payroll
    if p is None or not p.overtime_premium_pay:
        return []
    audited = _audited_net_of_duplicates(ctx)
    if audited < p.total_gross_wages - p.overtime_premium_pay / 2:
        return []  # audited payroll already appears to exclude the overtime premium
    low, high = _spread(ctx, p.overtime_premium_pay)
    the_rule = pick(ctx.audit.state, "NC.2C2A.OT", "NCCI.OT")
    return [
        Finding(
            "overtime_included",
            the_rule,
            "Overtime premium pay may not have been excluded",
            f"Payroll records show {p.overtime_premium_pay} of overtime premium pay and audited "
            f"payroll ({audited}) matches gross wages including it.",
            low,
            high,
            Decimal("0.65"),
            [p.evidence],
            ["Records show overtime separately by employee and summarized by class"],
        )
    ]


DETECTORS: tuple[Callable[[AnalysisContext], list[Finding]], ...] = (
    detect_line_arithmetic,
    detect_total_arithmetic,
    detect_mod_mismatch,
    detect_missing_credit,
    detect_duplicates,
    detect_payroll_mismatch,
    detect_overtime,
)


def run_detectors(ctx: AnalysisContext) -> list[Finding]:
    findings = [f for d in DETECTORS for f in d(ctx)]
    return [f for f in findings if f.impact_high >= MIN_IMPACT]

"""Run all detectors and produce a de-duplicated, range-based recovery estimate."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from compback_rating.detectors import Finding, implied_schedule_pct, run_detectors
from compback_rating.engine import Overrides, Recomputation, inputs_hash, recompute
from compback_rating.facts import AnalysisContext

EXACT_KINDS = {"line_arithmetic", "mod_mismatch", "missing_credit"}


@dataclass
class AnalysisResult:
    recomputation: Recomputation
    billed: Recomputation
    findings: list[Finding] = field(default_factory=list)
    inputs_hash: str = ""
    estimate_low: Decimal = Decimal(0)
    estimate_high: Decimal = Decimal(0)

    @property
    def customer_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.customer_visible]


def _joint_exact(ctx: AnalysisContext, findings: list[Finding]) -> Decimal:
    """Price all exact corrections together (captures interactions such as mod x credit)."""
    kinds = {f.detector for f in findings}
    if not kinds & EXACT_KINDS:
        return Decimal(0)
    adjustments = tuple(
        (i, Decimal(0))
        for i, ln in enumerate(ctx.audit.lines)
        if "line_arithmetic" in kinds and ln.printed_premium is not None
    )
    mod = ctx.worksheets[0].experience_mod if "mod_mismatch" in kinds else None
    pct = (
        ctx.declarations.schedule_credit_pct
        if ("missing_credit" in kinds and ctx.declarations)
        else implied_schedule_pct(ctx)
    )
    billed = recompute(ctx.audit, Overrides(use_printed_line_premiums=True)).total
    fixed = recompute(
        ctx.audit,
        Overrides(
            use_printed_line_premiums=True,
            experience_mod=mod,
            schedule_credit_pct=pct,
            payroll_adjustments=adjustments,
        ),
    ).total
    return billed - fixed


def analyze(ctx: AnalysisContext) -> AnalysisResult:
    findings = run_detectors(ctx)
    visible = [f for f in findings if f.customer_visible]
    exact = _joint_exact(ctx, [f for f in visible if f.detector in EXACT_KINDS])
    others = [f for f in visible if f.detector not in EXACT_KINDS]
    low = exact + sum((f.impact_low for f in others), Decimal(0))
    high = exact + sum((f.impact_high for f in others), Decimal(0))
    return AnalysisResult(
        recomputation=recompute(ctx.audit),
        billed=recompute(ctx.audit, Overrides(use_printed_line_premiums=True)),
        findings=sorted(findings, key=lambda f: (-f.impact_high, f.detector)),
        inputs_hash=inputs_hash(ctx.audit),
        estimate_low=max(low, Decimal(0)),
        estimate_high=max(high, Decimal(0)),
    )

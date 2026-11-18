"""Finding prioritization baseline (ML spec §6.2): expected recoverable value.

score = midpoint(impact range) x confidence x acceptance prior(detector)

Acceptance priors are hand-set baselines (documented assumptions, not data). They will be replaced
by a calibrated model trained on ``outcomes`` once enough resolved cases exist (time-based split).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ACCEPTANCE_PRIOR: dict[str, Decimal] = {
    # Arithmetic/document mismatches are easiest for a carrier to verify -> higher prior.
    "line_arithmetic": Decimal("0.9"),
    "manual_total": Decimal("0.9"),
    "total_premium": Decimal("0.85"),
    "mod_mismatch": Decimal("0.8"),
    "missing_credit": Decimal("0.6"),
    "overtime_included": Decimal("0.6"),
    "payroll_mismatch": Decimal("0.5"),
    "duplicate_class": Decimal("0.4"),
}
DEFAULT_PRIOR = Decimal("0.3")


def priority_score(
    detector: str, impact_low: Decimal, impact_high: Decimal, confidence: Decimal
) -> Decimal:
    midpoint = (impact_low + impact_high) / 2
    prior = ACCEPTANCE_PRIOR.get(detector, DEFAULT_PRIOR)
    return (midpoint * confidence * prior).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

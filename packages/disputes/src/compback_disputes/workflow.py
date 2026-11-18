"""Case state machine and fee calculation (pure functions; persisted by the API layer)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"ready_for_review", "withdrawn"}),
    "ready_for_review": frozenset({"approved_by_customer", "draft", "withdrawn"}),
    "approved_by_customer": frozenset({"submitted", "draft", "withdrawn"}),
    "submitted": frozenset({"carrier_responded", "withdrawn"}),
    "carrier_responded": frozenset({"resolved", "submitted", "withdrawn"}),
    "resolved": frozenset({"fee_invoiced", "closed"}),
    "fee_invoiced": frozenset({"closed"}),
    "closed": frozenset(),
    "withdrawn": frozenset(),
}


class InvalidTransitionError(ValueError):
    pass


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise InvalidTransitionError(f"cannot move a case from {current} to {target}")


CENT = Decimal("0.01")


@dataclass(frozen=True)
class FeeQuote:
    kind: str
    basis_amount: Decimal
    rate: Decimal | None
    gross: Decimal
    credit_applied: Decimal
    cap: Decimal | None
    amount: Decimal
    lines: list[str]


def contingency_fee(
    verified_recovery: Decimal,
    rate: Decimal,
    cap: Decimal,
    analysis_fee_paid: Decimal,
    credit_analysis_fee: bool,
) -> FeeQuote:
    """Fee on *verified* recovery only. Shown to the customer before they approve anything."""
    if verified_recovery < 0:
        raise ValueError("recovery cannot be negative")
    gross = (verified_recovery * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    capped = min(gross, cap)
    credit = min(analysis_fee_paid, capped) if credit_analysis_fee else Decimal(0)
    amount = capped - credit
    lines = [
        f"Verified recovery: ${verified_recovery:,.2f}",
        f"Contingency rate: {rate * 100:.2f}% -> ${gross:,.2f}",
    ]
    if capped < gross:
        lines.append(f"Capped at ${cap:,.2f}")
    if credit:
        lines.append(f"Less analysis fee already paid: -${credit:,.2f}")
    lines.append(f"Contingency fee due: ${amount:,.2f}")
    return FeeQuote("contingency", verified_recovery, rate, gross, credit, cap, amount, lines)


def analysis_fee(amount: Decimal) -> FeeQuote:
    return FeeQuote(
        "analysis",
        amount,
        None,
        amount,
        Decimal(0),
        None,
        amount,
        [f"Full analysis and dispute package: ${amount:,.2f}"],
    )

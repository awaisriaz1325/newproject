"""Money and decimal helpers. Floats are rejected everywhere money flows (ADR-0008)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer

CENT = Decimal("0.01")


class FloatMoneyError(ValueError):
    """Raised when a float is used where an exact decimal is required."""


def to_decimal(value: Any) -> Decimal:
    """Convert int/str/Decimal to Decimal. Floats and bools are refused (precision/ambiguity)."""
    if isinstance(value, bool):
        raise FloatMoneyError("booleans are not valid amounts")
    if isinstance(value, float):
        raise FloatMoneyError("floats are not allowed for money; pass a str or Decimal")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int | str):
        try:
            result = Decimal(str(value).replace(",", "").replace("$", "").strip())
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal amount: {value!r}") from exc
    else:
        raise TypeError(f"unsupported amount type: {type(value).__name__}")
    if not result.is_finite():
        raise ValueError("amount must be finite")
    return result


def round_cents(value: Decimal, rounding: str = ROUND_HALF_UP) -> Decimal:
    return value.quantize(CENT, rounding=rounding)


def format_usd(value: Decimal) -> str:
    q = round_cents(value)
    sign = "-" if q < 0 else ""
    return f"{sign}${abs(q):,.2f}"


ExactDecimal = Annotated[
    Decimal,
    BeforeValidator(to_decimal),
    PlainSerializer(str, return_type=str),
]
"""Pydantic type: accepts str/int/Decimal, rejects float, serializes as string."""

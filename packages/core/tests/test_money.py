from decimal import Decimal

import pytest
from compback_core.money import ExactDecimal, FloatMoneyError, format_usd, round_cents, to_decimal
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel


def test_rejects_float() -> None:
    with pytest.raises(FloatMoneyError):
        to_decimal(0.1)


def test_rejects_bool() -> None:
    with pytest.raises(FloatMoneyError):
        to_decimal(True)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("$1,234.50", Decimal("1234.50")), (" 7 ", Decimal("7")), (12, Decimal("12"))],
)
def test_parses_document_style_amounts(raw: str | int, expected: Decimal) -> None:
    assert to_decimal(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "NaN", "Infinity"])
def test_rejects_non_finite_or_garbage(raw: str) -> None:
    with pytest.raises(ValueError, match=r"decimal|finite"):
        to_decimal(raw)


def test_round_half_up() -> None:
    assert round_cents(Decimal("2.345")) == Decimal("2.35")
    assert round_cents(Decimal("-2.345")) == Decimal("-2.35")


def test_format_usd() -> None:
    assert format_usd(Decimal("-1234.5")) == "-$1,234.50"


class _M(BaseModel):
    amount: ExactDecimal


def test_pydantic_exact_decimal_roundtrip() -> None:
    m = _M.model_validate({"amount": "10.10"})
    assert m.amount == Decimal("10.10")
    assert m.model_dump(mode="json") == {"amount": "10.10"}
    with pytest.raises(ValueError, match="float"):
        _M.model_validate({"amount": 10.1})


@given(st.decimals(min_value=-(10**9), max_value=10**9, allow_nan=False, places=6))
def test_round_cents_is_idempotent(d: Decimal) -> None:
    assert round_cents(round_cents(d)) == round_cents(d)

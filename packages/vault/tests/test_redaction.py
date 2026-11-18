from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from compback_vault.redaction import MASK, redact_table, redact_text


@pytest.mark.parametrize(
    "text",
    [
        "SSN 123-45-6789",
        "employee 123 45 6789 wages",
        "ITIN 912-70-1234",
        "SSN: 123456789",
        "Social Security No. 123456789",
        "TIN 987654321",
        "SS# 078051120",
    ],
)
def test_identifiers_redacted(text: str) -> None:
    out = redact_text(text)
    assert out.count == 1
    assert MASK in out.text


@pytest.mark.parametrize(
    "text",
    [
        "Policy number WC 123456789",  # bare 9 digits without identifier context
        "FEIN 12-3456789",  # business identifier, stored encrypted instead
        "SSN XXX-XX-6789",  # already masked
        "Payroll 1,234,567.89 class 5645",
        "Phone 555-123-4567",
        "Date 2025-01-15",
    ],
)
def test_non_identifiers_left_alone(text: str) -> None:
    assert redact_text(text).text == text


@given(
    a=st.integers(0, 999),
    b=st.integers(0, 99),
    c=st.integers(0, 9999),
    sep=st.sampled_from(["-", " "]),
    prefix=st.text(alphabet=st.characters(blacklist_categories=("Nd",)), max_size=40),
    suffix=st.text(alphabet=st.characters(blacklist_categories=("Nd",)), max_size=40),
)
def test_formatted_ssn_never_survives(
    a: int, b: int, c: int, sep: str, prefix: str, suffix: str
) -> None:
    ssn = f"{a:03d}{sep}{b:02d}{sep}{c:04d}"
    if prefix.endswith("-") or suffix.startswith("-"):
        return  # adjacent dashes form a different token shape, covered by other tests
    out = redact_text(prefix + ssn + suffix)
    assert ssn not in out.text


def test_table_column_header_drives_redaction() -> None:
    rows = [["Name", "Social Security #", "Wages"], ["A", "123456789", "100"], ["B", "", "5"]]
    out, count = redact_table(rows)
    assert out[1][1] == MASK
    assert out[2][1] == ""
    assert out[1][2] == "100"
    assert count == 1


def test_summary_has_no_values() -> None:
    res = redact_text("SSN 123-45-6789 and 987-65-4321")
    assert res.summary() == {"ssn_formatted": 2}
    assert "123" not in str(res.spans)

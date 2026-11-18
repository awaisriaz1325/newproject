"""Golden + property tests.

Correct audits -> zero findings; injected errors -> found and priced right.
"""

from __future__ import annotations

import copy
import random
from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from compback_extract.synthetic import ERROR_KINDS, TEMPLATES, generate_case
from compback_rating.analysis import analyze
from compback_rating.engine import Overrides, r2, recompute
from compback_rating.rules import RULES, RuleStatus, validate_registry
from compback_rating.synthetic_context import context_from_case

STATES = ["FL", "NC", "TX"]
EXACT = {"line_arithmetic", "mod_mismatch", "missing_credit"}
DETECTOR_FOR = {
    "line_arithmetic": "line_arithmetic",
    "mod_mismatch": "mod_mismatch",
    "missing_credit": "missing_credit",
    "duplicate_class": "duplicate_class",
    "overtime_included": "overtime_included",
    "payroll_mismatch": "payroll_mismatch",
}


def _case(seed: int, errors: tuple[str, ...] = (), state: str | None = None):  # type: ignore[no-untyped-def]
    case = generate_case(seed, errors, TEMPLATES[seed % 3])
    if state:
        case.state = state
        case.lines = [replace(ln, state=state) for ln in case.lines]
    return case


def test_registry_is_valid() -> None:
    assert validate_registry() == []
    assert all(r.citations for r in RULES if r.status == RuleStatus.ACTIVE)


@pytest.mark.parametrize("seed", range(40))
def test_clean_cases_have_no_findings(seed: int) -> None:
    result = analyze(context_from_case(_case(seed)))
    assert result.findings == []
    assert result.estimate_high == 0
    # Engine reproduces the printed total exactly on a correct bill.
    case = _case(seed)
    assert result.billed.total == case.total_premium
    assert result.recomputation.total == case.total_premium


@pytest.mark.parametrize("kind", ERROR_KINDS)
@pytest.mark.parametrize("seed", range(15))
def test_single_injected_error_detected_with_correct_impact(kind: str, seed: int) -> None:
    case = _case(seed, (kind,), state="NC")
    injected = case.errors[0].overcharge
    result = analyze(context_from_case(case))
    hits = [f for f in result.findings if f.detector == DETECTOR_FOR[kind]]
    assert hits, f"{kind} not detected"
    finding = hits[0]
    if kind in EXACT:
        assert finding.impact_low == finding.impact_high == injected
    else:
        assert (
            finding.impact_low - Decimal("0.02")
            <= injected
            <= finding.impact_high + Decimal("0.02")
        )
    assert (
        result.estimate_low - Decimal("0.02") <= injected <= result.estimate_high + Decimal("0.02")
    )


@pytest.mark.parametrize("seed", range(20))
def test_two_exact_errors_joint_estimate_is_exact(seed: int) -> None:
    case = _case(seed, ("mod_mismatch", "missing_credit"), state="NC")
    correct = copy.deepcopy(case)
    correct.mod, correct.schedule_credit_applied = case.worksheet_mod, True
    injected = case.total_premium - correct.total_premium
    result = analyze(context_from_case(case))
    assert {"mod_mismatch", "missing_credit"} <= {f.detector for f in result.findings}
    assert abs(result.estimate_low - injected) <= Decimal("0.02")


def test_candidate_rules_never_reach_customer_numbers() -> None:
    case = _case(3, ("line_arithmetic",), state="FL")  # non-NC: line rule is a candidate
    result = analyze(context_from_case(case))
    line = next(f for f in result.findings if f.detector == "line_arithmetic")
    assert line.rule.id == "NCCI.LINE"
    assert not line.customer_visible
    assert line not in result.customer_findings
    assert result.estimate_high == 0


def test_nc_uses_verified_rule() -> None:
    result = analyze(context_from_case(_case(3, ("line_arithmetic",), state="NC")))
    line = next(f for f in result.findings if f.detector == "line_arithmetic")
    assert line.rule.id == "NC.3A1.LINE"
    assert line.customer_visible
    assert line.rule.citations[0].section == "Rule 3-A-1"


@pytest.mark.parametrize("seed", range(10))
def test_results_invariant_to_line_order(seed: int) -> None:
    case = _case(seed, ("mod_mismatch", "duplicate_class"), state="NC")
    ctx = context_from_case(case)
    base = analyze(ctx)
    lines = list(ctx.audit.lines)
    random.Random(seed).shuffle(lines)
    ctx.audit = replace(ctx.audit, lines=lines)
    shuffled = analyze(ctx)
    assert base.inputs_hash == shuffled.inputs_hash
    assert (base.estimate_low, base.estimate_high) == (
        shuffled.estimate_low,
        shuffled.estimate_high,
    )
    assert sorted(f.detector for f in base.findings) == sorted(
        f.detector for f in shuffled.findings
    )


def test_explanation_steps_cover_every_line_and_total() -> None:
    case = _case(5, state="NC")
    rec = recompute(context_from_case(case).audit)
    labels = [s.label for s in rec.steps]
    assert sum(lbl.startswith("Class ") for lbl in labels) == len(case.lines)
    assert labels[-1] == "Total premium"
    assert all(s.rule_id for s in rec.steps if s.label.startswith("Class "))


@settings(max_examples=200)
@given(
    payroll=st.decimals(min_value=0, max_value=10**7, places=2),
    rate=st.decimals(min_value=0, max_value=200, places=2),
)
def test_line_rounding_is_half_up_to_cents(payroll: Decimal, rate: Decimal) -> None:
    value = r2(payroll / 100 * rate)
    assert value == value.quantize(Decimal("0.01"))
    assert abs(value - payroll / 100 * rate) <= Decimal("0.005")


@settings(max_examples=100, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_property_clean_bills_reconcile(seed: int) -> None:
    case = generate_case(seed)
    ctx = context_from_case(case)
    assert (
        recompute(ctx.audit, Overrides(use_printed_line_premiums=True)).total == case.total_premium
    )
    assert analyze(ctx).customer_findings == []

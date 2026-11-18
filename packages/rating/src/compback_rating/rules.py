"""Rules registry (build rule §0.3): every rule has a jurisdiction scope, status and citation.

- ``active``: may produce customer-visible findings (still subject to reviewer confirmation).
- ``candidate``: may only produce internal "needs expert" findings; never customer-facing numbers.
- Consistency rules (``CONS.*``) compare the carrier's own documents with each other or with
  arithmetic; they interpret no rating rule, so they apply in every supported jurisdiction.

The registry lives in code (reviewed in pull requests, covered by tests) and every recomputation
stores ``REGISTRY_VERSION`` plus the rule ids it used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

REGISTRY_VERSION = "2026-11-18.1"
ALL = "*"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    RETIRED = "retired"


@dataclass(frozen=True)
class Citation:
    source: str
    section: str
    url: str | None
    effective_from: date | None
    retrieved: date


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    jurisdictions: frozenset[str]
    status: RuleStatus
    citations: tuple[Citation, ...]
    notes: str = ""
    tests: tuple[str, ...] = field(default_factory=tuple)

    def applies_to(self, state: str) -> bool:
        return ALL in self.jurisdictions or state in self.jurisdictions


_RETRIEVED = date(2026, 11, 18)
_NCRB_R2 = "https://www.ncrb.org/digitallibrary/basicmanual/Rule_2_-_Premium_and_Payroll.htm"
_NCRB_R3 = (
    "https://www.ncrb.org/digitallibrary/basicmanual/"
    "Rule_3_-_Ratings_and_Application_of_Premium_Elements.htm"
)
_CONSISTENCY = Citation(
    "Internal consistency of the policyholder's own carrier documents (no rating-rule "
    "interpretation)",
    "n/a",
    None,
    None,
    _RETRIEVED,
)

RULES: tuple[Rule, ...] = (
    Rule(
        "CONS.TOTALS",
        "Printed totals must equal the sum of their printed components",
        frozenset({ALL}),
        RuleStatus.ACTIVE,
        (_CONSISTENCY,),
        tests=("test_golden_line_arithmetic", "test_clean_cases_have_no_findings"),
    ),
    Rule(
        "CONS.MOD",
        "Experience mod on the bill must match the experience rating worksheet for the same period",
        frozenset({ALL}),
        RuleStatus.ACTIVE,
        (_CONSISTENCY,),
        tests=("test_golden_mod_mismatch",),
    ),
    Rule(
        "CONS.CREDIT",
        "Credits promised on the policy/quote should appear on the final bill",
        frozenset({ALL}),
        RuleStatus.ACTIVE,
        (_CONSISTENCY,),
        notes="A credit can be legitimately withdrawn mid-term; reviewer must confirm.",
        tests=("test_golden_missing_credit",),
    ),
    Rule(
        "CONS.PAYROLL",
        "Audited payroll should not exceed the employer's payroll records",
        frozenset({ALL}),
        RuleStatus.ACTIVE,
        (_CONSISTENCY,),
        notes="Records may cover different periods/entities; reviewer must confirm scope.",
        tests=("test_golden_payroll_mismatch",),
    ),
    Rule(
        "CONS.DUPLICATE",
        "The same class and payroll should not be charged twice",
        frozenset({ALL}),
        RuleStatus.ACTIVE,
        (_CONSISTENCY,),
        notes="Identical lines can be legitimate (separate locations); low confidence.",
        tests=("test_golden_duplicate_class",),
    ),
    Rule(
        "NC.3A1.LINE",
        "Manual premium = payroll / 100 x manual rate",
        frozenset({"NC"}),
        RuleStatus.ACTIVE,
        (
            Citation(
                "NCRB North Carolina Basic Manual",
                "Rule 3-A-1",
                _NCRB_R3,
                date(2024, 4, 1),
                _RETRIEVED,
            ),
        ),
    ),
    Rule(
        "NCCI.LINE",
        "Manual premium = payroll / 100 x manual rate (non-NC states)",
        frozenset({ALL}),
        RuleStatus.CANDIDATE,
        (),
        notes="UNVERIFIED outside NC: widely described, primary NCCI text not yet reviewed. "
        "Some classes use a non-payroll basis (e.g. per capita).",
        tests=("test_golden_line_arithmetic",),
    ),
    Rule(
        "NC.3A.ORDER",
        "Order: manual -> experience & schedule mods -> standard premium -> "
        "premium discount; expense constant not subject to mod or discount",
        frozenset({"NC"}),
        RuleStatus.ACTIVE,
        (
            Citation(
                "NCRB North Carolina Basic Manual",
                "Rules 3-A-10, 3-A-18, 3-A-19",
                _NCRB_R3,
                date(2024, 4, 1),
                _RETRIEVED,
            ),
        ),
    ),
    Rule(
        "NC.2C2A.OT",
        "Overtime: extra pay excluded when records show it separately by "
        "employee and by class (1/3 of total pay at time-and-a-half; 1/2 at double time)",
        frozenset({"NC"}),
        RuleStatus.ACTIVE,
        (
            Citation(
                "NCRB North Carolina Basic Manual",
                "Rule 2-C-2-a",
                _NCRB_R2,
                date(2024, 1, 1),
                _RETRIEVED,
            ),
        ),
        tests=("test_golden_overtime",),
    ),
    Rule(
        "NCCI.OT",
        "Overtime premium pay excluded from payroll (non-NC states)",
        frozenset({ALL}),
        RuleStatus.CANDIDATE,
        (),
        notes="UNVERIFIED: secondary sources only; state rules and record-keeping conditions vary.",
        tests=("test_golden_overtime",),
    ),
    Rule(
        "NC.2H.SUB",
        "Additional premium only for employees of *uninsured* subcontractors",
        frozenset({"NC"}),
        RuleStatus.ACTIVE,
        (
            Citation(
                "NCRB North Carolina Basic Manual",
                "Rule 2-H-1, 2-H-2",
                _NCRB_R2,
                date(2024, 1, 1),
                _RETRIEVED,
            ),
        ),
    ),
    Rule(
        "NCCI.SUB",
        "Uninsured-subcontractor charge despite valid certificates (non-NC)",
        frozenset({ALL}),
        RuleStatus.CANDIDATE,
        (),
        notes="UNVERIFIED outside NC.",
    ),
    Rule(
        "NC.2E1B.EXEC",
        "Executive officer payroll subject to state minimum/maximum",
        frozenset({"NC"}),
        RuleStatus.CANDIDATE,
        (
            Citation(
                "NCRB North Carolina Basic Manual",
                "Rule 2-E-1-b",
                _NCRB_R2,
                date(2024, 1, 1),
                _RETRIEVED,
            ),
        ),
        notes="Limit values live in the Miscellaneous Values section and are not loaded yet.",
    ),
    Rule(
        "ML.CLASS_REVIEW",
        "Class code may not match described operations (expert review)",
        frozenset({ALL}),
        RuleStatus.CANDIDATE,
        (),
        notes="Never asserted as an error; output is 'needs expert review'.",
    ),
)

REGISTRY: dict[str, Rule] = {r.id: r for r in RULES}


def rule(rule_id: str) -> Rule:
    return REGISTRY[rule_id]


def pick(state: str, active_id: str, fallback_id: str) -> Rule:
    """Use the jurisdiction-specific verified rule when it applies, else the fallback."""
    r = REGISTRY[active_id]
    return r if r.applies_to(state) else REGISTRY[fallback_id]


def validate_registry() -> list[str]:
    """Problems that must block a release (also run as a test)."""
    problems = []
    for r in RULES:
        if r.status == RuleStatus.ACTIVE and not r.citations:
            problems.append(f"{r.id}: active rule without citation")
        if r.status == RuleStatus.ACTIVE and not r.jurisdictions:
            problems.append(f"{r.id}: active rule without jurisdiction")
    return problems

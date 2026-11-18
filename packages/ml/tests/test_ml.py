from __future__ import annotations

from decimal import Decimal

from compback_ml.class_review import ClassCodeAssistant, PlaceholderReferenceProvider, top_k_recall
from compback_ml.prioritize import priority_score
from compback_ml.quality import edit_rates

# Small, self-written labeled set (not real employer data). Used to measure the baseline.
LABELED = [
    ("We install and repair asphalt shingle roofs on houses", "5551"),
    ("Office manager handles bookkeeping and reception", "8810"),
    ("Crew mows lawns, plants trees and maintains grounds", "0042"),
    ("Electricians wire new homes and commercial buildings", "5190"),
    ("Framing crew builds wood houses", "5645"),
    ("Delivery drivers haul materials by truck", "7380"),
    ("Plumbers install water heaters and fix drains", "5183"),
    ("CNC machining of metal parts on lathes and mills", "3632"),
    ("Sales rep visits customers to estimate jobs", "8742"),
    ("Interior and exterior house painting and drywall finishing", "5474"),
    ("Nightly janitorial cleaning of office buildings", "9014"),
    ("Concrete forms and framing for commercial buildings", "5403"),
]


def test_placeholder_provider_is_not_production_licensed() -> None:
    assert PlaceholderReferenceProvider.licensed_for_production is False


def test_baseline_top3_recall_on_labeled_set() -> None:
    assistant = ClassCodeAssistant(PlaceholderReferenceProvider())
    recall = top_k_recall(assistant, LABELED, k=3)
    assert recall >= 0.9, recall  # measured: see docs/ml/class-code-assistant.md


def test_review_never_asserts_wrong_only_flags() -> None:
    assistant = ClassCodeAssistant(PlaceholderReferenceProvider())
    ok = assistant.review("5551", "roofing crew replacing shingles", "NC")
    assert not ok.needs_expert_review
    flagged = assistant.review("8810", "roofing crew replacing shingles on houses", "NC")
    assert flagged.needs_expert_review
    assert "does not mean" in flagged.disclaimer
    assert flagged.suggestions[0].code == "5551"


def test_priority_prefers_higher_value_and_confidence() -> None:
    a = priority_score("mod_mismatch", Decimal(1000), Decimal(1000), Decimal("0.9"))
    b = priority_score("duplicate_class", Decimal(0), Decimal(1000), Decimal("0.5"))
    assert a > b > 0


def test_edit_rates() -> None:
    exts = [("e1", "heuristic-v1", "premium_audit"), ("e2", "heuristic-v1", "premium_audit")]
    edits = [
        ("e1", "class_lines[0].payroll"),
        ("e1", "class_lines[2].payroll"),
        ("e2", "class_lines[1].payroll"),
        ("e2", "total_premium"),
    ]
    rates = {q.field: q.edit_rate for q in edit_rates(exts, edits)}
    assert rates == {"class_lines[].payroll": 1.0, "total_premium": 0.5}

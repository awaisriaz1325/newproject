"""Baseline document classifier: weighted keyword evidence over redacted page text.

Deterministic and explainable; the LLM classifier (when configured) must agree with or override it
with higher confidence. Unknown is a valid answer — it routes the document to human review.
Also detects arrangements CompBack declines in v1 (PEO / employee leasing, self-insurance,
retrospective rating, large deductible).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SIGNALS: dict[str, list[tuple[str, float]]] = {
    "premium_audit": [
        (r"premium audit", 3),
        (r"audit(ed)? (payroll|exposure|premium)", 2),
        (r"final audit", 3),
        (r"auditor", 1),
    ],
    "audit_billing": [
        (r"audit (billing|adjustment|invoice)", 3),
        (r"return premium", 1),
        (r"additional premium due", 2),
    ],
    "policy_declarations": [
        (r"information page", 3),
        (r"declarations", 3),
        (r"item 3\.?a", 2),
        (r"estimated (annual )?premium", 1),
    ],
    "quote": [(r"\bquot(e|ation)\b", 3), (r"proposal", 1)],
    "experience_rating": [
        (r"experience rating (worksheet|calculation)", 4),
        (r"experience modification", 2),
        (r"\bmod(ification)? factor", 1),
        (r"expected losses", 2),
    ],
    "payroll_register": [
        (r"payroll (register|summary|journal)", 3),
        (r"gross (pay|wages)", 1),
        (r"\bovertime\b", 1),
        (r"\bnet pay\b", 1),
    ],
    "payroll_tax_form": [
        (r"form 941", 4),
        (r"employer'?s quarterly federal tax return", 4),
        (r"wages, tips,? and other compensation", 2),
    ],
    "certificate_of_insurance": [
        (r"certificate of (liability )?insurance", 4),
        (r"acord 25", 3),
        (r"certificate holder", 2),
    ],
    "carrier_correspondence": [(r"dear (policyholder|insured)", 2), (r"sincerely", 1)],
}
_COMPILED = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in _SIGNALS.items()}

_DECLINE = {
    "peo": re.compile(
        r"(professional employer organi[sz]ation|\bPEO\b|employee leasing|"
        r"labor contractor endorsement)",
        re.I,
    ),
    "self_insured": re.compile(r"self[- ]insur(ed|ance)", re.I),
    "retrospective_rating": re.compile(r"retrospective (rating|premium)", re.I),
    "large_deductible": re.compile(r"large deductible", re.I),
}
_PERIOD = re.compile(
    r"(?P<a>\d{1,2}/\d{1,2}/\d{2,4})\s*(?:-|to|through|thru)\s*(?P<b>\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)


@dataclass(frozen=True)
class Classification:
    doc_type: str
    confidence: float
    scores: dict[str, float]
    decline_reasons: list[str]
    period: tuple[str, str] | None


def classify_text(text: str) -> Classification:
    head = text[:6000]
    scores = {k: sum(w for rx, w in rules if rx.search(head)) for k, rules in _COMPILED.items()}
    best = max(scores, key=lambda k: scores[k])
    ranked = sorted(scores.values(), reverse=True)
    top, second = ranked[0], ranked[1]
    if top < 3:
        doc_type, confidence = "unknown", 0.0
    else:
        doc_type = best
        confidence = round(min(0.95, 0.5 + 0.1 * top) * (1 - 0.5 * (second / top)), 2)
    declines = [name for name, rx in _DECLINE.items() if rx.search(text)]
    match = _PERIOD.search(head)
    return Classification(
        doc_type, confidence, scores, declines, (match["a"], match["b"]) if match else None
    )

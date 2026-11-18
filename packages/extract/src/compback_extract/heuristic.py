"""Baseline premium-audit extractor over redacted page text (no LLM, deterministic).

Generic rules rather than per-carrier templates: labelled totals, and class lines detected as a
class-code token plus at least three amounts. When a header row names the columns, values are
assigned by header order; otherwise payroll/rate/premium are inferred by arithmetic consistency.
It is the fallback when no LLM is configured, and the baseline the LLM must beat.
"""

from __future__ import annotations

import re
from decimal import Decimal
from itertools import permutations

from compback_extract.schemas import ClassLine, Fld, PremiumAuditV1, to_decimal

NUM = r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?"
_NUM_RE = re.compile(NUM)
_CODE_RE = re.compile(r"(?<![\d.,])(\d{4})(?![\d.,])")
_STATE_RE = re.compile(r"\b([A-Z]{2})\b")
_DATE = r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}"

_LABELS: dict[str, list[str]] = {
    "total_manual_premium": [r"total manual premium", r"manual premium total"],
    "experience_mod": [r"experience mod(ification)?( factor)?", r"\bmod factor"],
    "expense_constant": [r"expense constant"],
    "total_premium": [r"total (audited |final )?premium"],
    "previously_billed": [r"previously billed", r"deposit premium", r"estimated premium paid"],
    "balance": [r"additional premium due", r"return premium", r"balance due", r"amount due"],
}


def _labelled(text: str, patterns: list[str], page: int) -> Fld:
    for pat in patterns:
        m = re.search(rf"(?im)^.*?{pat}\s*[:\-]?\s*({NUM})", text)
        if m:
            raw = m.group(m.lastindex or 1)
            value = to_decimal(raw)
            if value is not None:
                if re.search(r"(?i)return premium", m.group(0)) and value > 0:
                    value = -value
                return Fld(value=str(value), page=page, confidence=0.8)
    return Fld()


def _text_field(text: str, pattern: str, page: int) -> Fld:
    m = re.search(pattern, text, re.I | re.M)
    return Fld(value=m.group(1).strip(), page=page, confidence=0.8) if m else Fld()


def _header_order(line: str) -> list[str] | None:
    low = line.lower()
    cols = {
        "payroll": low.find("payroll") if "payroll" in low else low.find("exposure"),
        "rate": low.find("rate"),
        "premium": low.find("premium"),
    }
    if min(cols.values()) < 0:
        return None
    return sorted(cols, key=lambda k: cols[k])


def _assign(
    nums: list[Decimal], order: list[str] | None
) -> tuple[Decimal, Decimal, Decimal, float]:
    if order and len(nums) >= 3:
        mapped = dict(zip(order, nums[:3], strict=True))
        payroll, rate, premium = mapped["payroll"], mapped["rate"], mapped["premium"]
        ok = abs(payroll / 100 * rate - premium) <= Decimal("0.5")
        return payroll, rate, premium, 0.9 if ok else 0.7
    for a, b, c in permutations(nums[:3]):
        if abs(a / 100 * b - c) <= Decimal("0.5") and b < 100:
            return a, b, c, 0.75
    a, b, c = nums[:3]
    return a, b, c, 0.4


def extract_premium_audit(pages: list[str]) -> PremiumAuditV1:  # noqa: PLR0912
    doc = PremiumAuditV1()
    order: list[str] | None = None
    for page_no, text in enumerate(pages, start=1):
        if doc.carrier_name.value is None:
            doc.carrier_name = _text_field(text, r"carrier\s*:\s*(.+)$", page_no)
        if doc.policy_number.value is None:
            doc.policy_number = _text_field(
                text, r"policy (?:no\.?|number|#)\s*:?\s*(\S+)", page_no
            )
        if doc.period_start.value is None:
            m = re.search(rf"({_DATE})\s*(?:to|-|through|thru)\s*({_DATE})", text)
            if m:
                doc.period_start = Fld(value=m.group(1), page=page_no, confidence=0.8)
                doc.period_end = Fld(value=m.group(2), page=page_no, confidence=0.8)
        for name, pats in _LABELS.items():
            if getattr(doc, name).value is None:
                setattr(doc, name, _labelled(text, pats, page_no))
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if re.search(
                r"(?i)(payroll|exposure).*rate.*premium|rate.*(payroll|exposure)", line
            ) and not _NUM_RE.search(line):
                order = _header_order(line)
                continue
            if re.search(
                r"(?i)^\s*(total|experience|schedule|expense|previously|additional|"
                r"return|balance|policy|state:)",
                line,
            ):
                continue
            code_m = _CODE_RE.search(line)
            if not code_m:
                continue
            candidate = line
            if line.lower().startswith("class code") and idx + 1 < len(lines):
                candidate = line + " " + lines[idx + 1]  # worksheet layout: values on next line
            tail = candidate.replace(code_m.group(1), " ", 1)
            nums = [d for d in (to_decimal(t) for t in _NUM_RE.findall(tail)) if d is not None]
            nums = [n for n in nums if n != 0]
            if len(nums) < 3:
                continue
            labelled = re.search(
                rf"(?i)payroll:\s*({NUM}).*rate:\s*({NUM}).*premium:\s*({NUM})", candidate
            )
            if labelled:
                vals = [to_decimal(g) for g in labelled.groups()]
                if None not in vals:
                    payroll, rate, premium = (v for v in vals if v is not None)
                    conf = 0.9
                else:
                    continue
            else:
                payroll, rate, premium, conf = _assign(nums, order)
            state_m = _STATE_RE.search(candidate.replace("LLC", ""))
            desc_m = re.search(
                r"\d{4}\s+([A-Za-z][A-Za-z ,\-&/]+?)(?:\s{2,}|\s+State:|\s+\d|$)", candidate
            )
            doc.class_lines.append(
                ClassLine(
                    state=state_m.group(1) if state_m else None,
                    class_code=code_m.group(1),
                    description=desc_m.group(1).strip() if desc_m else None,
                    payroll=str(payroll),
                    rate=str(rate),
                    premium=str(premium),
                    page=page_no,
                    confidence=conf,
                )
            )
    return doc

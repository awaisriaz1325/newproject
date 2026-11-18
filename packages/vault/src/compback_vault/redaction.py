"""SSN / ITIN / individual TIN detection and redaction (ADR-0005).

Policy (documented, tested):
- Formatted SSN/ITIN patterns (``123-45-6789``, ``123 45 6789``) are always redacted, including
  values that fail SSA validity rules: over-redaction of a 3-2-4 pattern is the safe direction.
- Bare 9-digit numbers are redacted when an identifier keyword (SSN, social security, TIN, ITIN,
  taxpayer id, SS#) appears shortly before them, or when they are in a column/row labelled as such.
- EINs (``12-3456789``) are business identifiers needed for matching policies; they are NOT
  redacted here and are stored encrypted (restricted field) instead.
- Already-masked values (``XXX-XX-1234``, ``***-**-1234``) are left alone.

The redactor returns only spans and counts, never the matched values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MASK = "[REDACTED-TIN]"
_SEP_SSN = re.compile(r"(?<![\d-])(\d{3})([- ])(\d{2})\2(\d{4})(?![\d-])")
_BARE9 = re.compile(r"(?<![\d-])\d{9}(?![\d-])")
_KEYWORD = re.compile(
    r"(ssn|s\.s\.n|social\s*sec(urity)?(\s*(no|num|number|#))?|ss\s*#|\btin\b|\bitin\b|"
    r"taxpayer\s*(id|identification)|tax\s*id\s*(no|number|#)?)",
    re.IGNORECASE,
)
KEYWORD_WINDOW = 40


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str  # "ssn_formatted" | "tin_contextual"


@dataclass
class RedactionResult:
    text: str
    spans: list[Span] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.spans)

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.spans:
            out[s.kind] = out.get(s.kind, 0) + 1
        return out


def find_spans(text: str, *, column_is_tin: bool = False) -> list[Span]:
    spans = [Span(m.start(), m.end(), "ssn_formatted") for m in _SEP_SSN.finditer(text)]
    taken = [(s.start, s.end) for s in spans]
    for m in _BARE9.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        window = text[max(0, m.start() - KEYWORD_WINDOW) : m.start()]
        if column_is_tin or _KEYWORD.search(window):
            spans.append(Span(m.start(), m.end(), "tin_contextual"))
    return sorted(spans, key=lambda s: s.start)


def redact_text(text: str, *, column_is_tin: bool = False) -> RedactionResult:
    spans = find_spans(text, column_is_tin=column_is_tin)
    if not spans:
        return RedactionResult(text=text)
    parts: list[str] = []
    cursor = 0
    for span in spans:
        parts.append(text[cursor : span.start])
        parts.append(MASK)
        cursor = span.end
    parts.append(text[cursor:])
    return RedactionResult(text="".join(parts), spans=spans)


def is_tin_header(cell: str) -> bool:
    return bool(_KEYWORD.search(cell))


def redact_table(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    """Redact tabular data (CSV/XLSX). Columns whose header names an identifier are fully masked."""
    if not rows:
        return rows, 0
    header = rows[0]
    tin_cols = {i for i, h in enumerate(header) if is_tin_header(h)}
    count = 0
    out = [list(header)]
    for row in rows[1:]:
        new_row = []
        for i, cell in enumerate(row):
            if i in tin_cols and cell.strip() and any(ch.isdigit() for ch in cell):
                new_row.append(MASK)
                count += 1
                continue
            res = redact_text(cell)
            count += res.count
            new_row.append(res.text)
        out.append(new_row)
    return out, count

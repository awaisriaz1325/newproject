"""Dispute package generator: cover letter + itemized schedule, as PDF and editable DOCX.

Every number and citation comes from confirmed finding records (engine + rules registry) and is
validated before rendering. Wording is deterministic templates; legal language is a placeholder for
attorney review. The customer (or their own advisor) submits the package — never CompBack.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = (
    "[ATTORNEY REVIEW REQUIRED — PLACEHOLDER] This schedule was prepared with CompBack software "
    "from documents provided by the policyholder. Amounts are estimates based on the carrier's own "
    "documents and are not guaranteed. This is not legal advice."
)


@dataclass(frozen=True)
class PackageItem:
    finding_id: str
    title: str
    explanation: str
    impact_low: Decimal
    impact_high: Decimal
    evidence: str
    citation: str


@dataclass(frozen=True)
class PackageInput:
    employer_name: str
    carrier_name: str
    policy_number: str
    period: str
    prepared_on: date
    items: list[PackageItem]


class PackageValidationError(ValueError):
    pass


def money(v: Decimal) -> str:
    return f"${v:,.2f}"


def totals(inp: PackageInput) -> tuple[Decimal, Decimal]:
    return (
        sum((i.impact_low for i in inp.items), Decimal(0)),
        sum((i.impact_high for i in inp.items), Decimal(0)),
    )


def validate(inp: PackageInput) -> None:
    if not inp.items:
        raise PackageValidationError("a dispute package needs at least one confirmed finding")
    for item in inp.items:
        if item.impact_low < 0 or item.impact_low > item.impact_high:
            raise PackageValidationError(f"invalid impact range on {item.finding_id}")
        if not item.citation.strip() or not item.evidence.strip():
            raise PackageValidationError(f"missing citation/evidence on {item.finding_id}")


def _amount(item: PackageItem) -> str:
    if item.impact_low == item.impact_high:
        return money(item.impact_high)
    return f"{money(item.impact_low)} - {money(item.impact_high)}"


def letter_paragraphs(inp: PackageInput) -> list[str]:
    low, high = totals(inp)
    rng = money(high) if low == high else f"{money(low)} to {money(high)}"
    return [
        f"Date: {inp.prepared_on:%B %d, %Y}",
        f"To: {inp.carrier_name} — Premium Audit Department",
        f"Re: Request for premium audit review — Policy {inp.policy_number}, period {inp.period}",
        f"{inp.employer_name} requests a review of the final premium audit for the policy above. "
        f"Our review of your audit statement and our records identified {len(inp.items)} "
        f"item(s), listed in the attached schedule, which we estimate affect the premium by "
        f"{rng}.",
        "For each item, the schedule shows what we found, where it appears in your documents, and "
        "our estimate of the effect. Please review these items, correct the audit where "
        "appropriate, and send a revised audit billing or explain your determination in writing.",
        "Sincerely,",
        f"{inp.employer_name}",
    ]


def render_pdf(inp: PackageInput) -> bytes:
    validate(inp)
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        title=f"Premium audit review request {inp.policy_number}",
    )
    story: list[object] = [Paragraph(p, styles["Normal"]) for p in letter_paragraphs(inp)]
    story += [Spacer(1, 18), Paragraph("Schedule of items", styles["Heading2"])]
    rows: list[list[object]] = [["#", "Item", "Evidence", "Estimated effect"]]
    for n, item in enumerate(inp.items, start=1):
        rows.append(
            [
                str(n),
                Paragraph(
                    f"<b>{item.title}</b><br/>{item.explanation}<br/><i>Basis: {item.citation}</i>",
                    styles["BodyText"],
                ),
                Paragraph(item.evidence, styles["BodyText"]),
                _amount(item),
            ]
        )
    low, high = totals(inp)
    rows.append(
        [
            "",
            "Total (estimated)",
            "",
            money(high) if low == high else f"{money(low)} - {money(high)}",
        ]
    )
    table = Table(rows, colWidths=[0.3 * inch, 3.6 * inch, 1.6 * inch, 1.4 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, "#999999"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), "#EEEEEE"),
            ]
        )
    )
    story += [table, Spacer(1, 18), Paragraph(DISCLAIMER, styles["Italic"])]
    doc.build(story)
    return buf.getvalue()


def render_docx(inp: PackageInput) -> bytes:
    validate(inp)
    d = DocxDocument()
    for p in letter_paragraphs(inp):
        d.add_paragraph(p)
    d.add_heading("Schedule of items", level=2)
    table = d.add_table(rows=1, cols=4)
    for cell, text in zip(
        table.rows[0].cells, ["#", "Item", "Evidence", "Estimated effect"], strict=True
    ):
        cell.text = text
    for n, item in enumerate(inp.items, start=1):
        cells = table.add_row().cells
        cells[0].text = str(n)
        cells[1].text = f"{item.title}\n{item.explanation}\nBasis: {item.citation}"
        cells[2].text = item.evidence
        cells[3].text = _amount(item)
    d.add_paragraph(DISCLAIMER)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def content_hash(inp: PackageInput) -> str:
    parts = [inp.policy_number, inp.period] + [
        f"{i.finding_id}|{i.impact_low}|{i.impact_high}|{i.citation}" for i in inp.items
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

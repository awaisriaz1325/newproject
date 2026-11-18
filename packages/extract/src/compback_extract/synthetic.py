"""Synthetic premium-audit generator for tests and evaluation. ALL DATA IS FICTIONAL.

Every generated page carries a "SYNTHETIC SAMPLE - FICTIONAL DATA" banner. Class codes, rates and
factors are random illustrative numbers, NOT real filed rates. Each case records ground truth and
any injected errors with their exact dollar effect, so detectors can be golden-tested.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from compback_extract.schemas import Charge, ClassLine, Fld, PremiumAuditV1

BANNER = "SYNTHETIC SAMPLE - FICTIONAL DATA - NOT A REAL POLICY"
CENT = Decimal("0.01")
ONE = Decimal(1)
_NAMES = [
    "Ridgeline",
    "Bluebird",
    "Cedar Point",
    "Ironwood",
    "Harbor",
    "Summit",
    "Maple Ave",
    "Granite",
    "Prairie",
    "Lakeshore",
]
_TRADES = ["Roofing", "Restoration", "Landscaping", "Electric", "Fabrication", "Builders"]
_CARRIERS = [
    "Example Mutual Casualty Co (Fictional)",
    "Sample Indemnity Insurance (Fictional)",
    "Demo Workers Insurance Exchange (Fictional)",
]
# Illustrative only. Real codes/rates vary by state and are not used.
_CLASSES = [
    ("5645", "Carpentry - residential"),
    ("5551", "Roofing"),
    ("0042", "Landscaping"),
    ("5190", "Electrical wiring"),
    ("3632", "Machine shop"),
    ("8810", "Clerical office"),
    ("8742", "Outside sales"),
    ("5403", "Carpentry - commercial"),
]
STATES = ["FL", "GA", "TX", "AZ", "TN", "CO"]
TEMPLATES = ("statement", "worksheet", "billing")
ERROR_KINDS = (
    "line_arithmetic",
    "mod_mismatch",
    "missing_credit",
    "duplicate_class",
    "overtime_included",
    "payroll_mismatch",
)


def q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Line:
    state: str
    code: str
    description: str
    payroll: Decimal
    rate: Decimal

    @property
    def premium(self) -> Decimal:
        return q(self.payroll / 100 * self.rate)


@dataclass
class InjectedError:
    kind: str
    description: str
    overcharge: Decimal  # exact dollar effect on total premium (positive = customer overcharged)


@dataclass
class SyntheticCase:
    case_id: str
    employer_name: str
    carrier: str
    policy_number: str
    state: str
    period_start: date
    period_end: date
    template: str
    lines: list[Line]
    mod: Decimal  # mod actually printed and applied on the bill
    worksheet_mod: Decimal  # mod on the experience rating worksheet (truth)
    schedule_credit_pct: Decimal  # promised on declarations, e.g. 0.10 for 10%
    schedule_credit_applied: bool
    expense_constant: Decimal
    previously_billed: Decimal
    overtime_premium_pay: Decimal  # OT premium portion recorded in payroll records
    payroll_records_total: Decimal  # gross payroll per payroll register (truth)
    printed_line_premiums: dict[int, Decimal] = field(default_factory=dict)
    errors: list[InjectedError] = field(default_factory=list)

    # -------- computed amounts exactly as the bill prints them (errors included)
    def line_premium(self, i: int) -> Decimal:
        return self.printed_line_premiums.get(i, self.lines[i].premium)

    @property
    def manual_premium(self) -> Decimal:
        return sum((self.line_premium(i) for i in range(len(self.lines))), Decimal(0))

    @property
    def modified_premium(self) -> Decimal:
        return q(self.manual_premium * self.mod)

    @property
    def schedule_amount(self) -> Decimal:
        if not self.schedule_credit_applied:
            return Decimal(0)
        return -q(self.modified_premium * self.schedule_credit_pct)

    @property
    def total_premium(self) -> Decimal:
        return self.modified_premium + self.schedule_amount + self.expense_constant

    @property
    def balance(self) -> Decimal:
        return self.total_premium - self.previously_billed

    def truth(self) -> PremiumAuditV1:
        """Ground-truth extraction: what is printed on the page (errors included)."""

        def f(v: object) -> Fld:
            return Fld(value=str(v), page=1, confidence=1.0)

        return PremiumAuditV1(
            carrier_name=f(self.carrier),
            policy_number=f(self.policy_number),
            period_start=f(self.period_start.isoformat()),
            period_end=f(self.period_end.isoformat()),
            audit_type=f("final"),
            class_lines=[
                ClassLine(
                    state=ln.state,
                    class_code=ln.code,
                    description=ln.description,
                    payroll=str(ln.payroll),
                    rate=str(ln.rate),
                    premium=str(self.line_premium(i)),
                    page=1,
                    confidence=1.0,
                )
                for i, ln in enumerate(self.lines)
            ],
            total_manual_premium=f(self.manual_premium),
            experience_mod=f(self.mod),
            schedule_mod=f(self.schedule_amount) if self.schedule_credit_applied else Fld(),
            premium_discount=Fld(),
            expense_constant=f(self.expense_constant),
            other_charges=[]
            if not self.schedule_credit_applied
            else [
                Charge(
                    label="Schedule credit",
                    amount=str(self.schedule_amount),
                    page=1,
                    confidence=1.0,
                )
            ],
            total_premium=f(self.total_premium),
            previously_billed=f(self.previously_billed),
            balance=f(self.balance),
        )


def _money(rng: random.Random, low: int, high: int) -> Decimal:
    return Decimal(rng.randrange(low, high)) * 100 + Decimal(rng.randrange(0, 100)) / 100


def generate_case(
    seed: int, errors: tuple[str, ...] = (), template: str | None = None
) -> SyntheticCase:
    rng = random.Random(seed)
    state = rng.choice(STATES)
    start = date(2024, 1, 1) + timedelta(days=rng.randrange(0, 360))
    picks = rng.sample(_CLASSES, rng.randint(2, 4))
    lines = [
        Line(state, code, desc, _money(rng, 300, 4000), Decimal(rng.randrange(150, 1800)) / 100)
        for code, desc in picks
    ]
    ot = q(sum((ln.payroll for ln in lines), Decimal(0)) * Decimal(rng.randrange(1, 6)) / 100)
    case = SyntheticCase(
        case_id=f"SYN-{seed:05d}",
        employer_name=f"{rng.choice(_NAMES)} {rng.choice(_TRADES)} LLC (Fictional)",
        carrier=rng.choice(_CARRIERS),
        policy_number=f"WC-{rng.randrange(10**6, 10**7)}-SYN",
        state=state,
        period_start=start,
        period_end=start + timedelta(days=365),
        template=template or rng.choice(TEMPLATES),
        lines=lines,
        mod=Decimal(rng.randrange(78, 130)) / 100,
        worksheet_mod=Decimal(0),
        schedule_credit_pct=Decimal(rng.choice([0, 5, 10, 15])) / 100,
        schedule_credit_applied=True,
        expense_constant=Decimal(rng.choice([160, 200, 250])),
        previously_billed=Decimal(0),
        overtime_premium_pay=ot,
        payroll_records_total=sum((ln.payroll for ln in lines), Decimal(0)) + ot,
    )
    case.worksheet_mod = case.mod
    if case.schedule_credit_pct == 0:
        case.schedule_credit_applied = False
    for kind in errors:
        _inject(case, kind, rng)
    case.previously_billed = q(case.total_premium * Decimal(rng.randrange(70, 110)) / 100)
    return case


def _inject(case: SyntheticCase, kind: str, rng: random.Random) -> None:
    if kind == "missing_credit" and case.schedule_credit_pct == 0:
        case.schedule_credit_pct = Decimal("0.10")  # the policy promised a credit...
        case.schedule_credit_applied = True  # ...so the correct bill includes it
    before = case.total_premium
    if kind == "line_arithmetic":
        i = rng.randrange(len(case.lines))
        case.printed_line_premiums[i] = case.lines[i].premium + Decimal(rng.randrange(50, 900))
        desc = f"Class {case.lines[i].code} premium does not equal payroll x rate / 100"
    elif kind == "mod_mismatch":
        case.mod = case.worksheet_mod + Decimal(rng.randrange(5, 25)) / 100
        desc = f"Bill applies mod {case.mod}, worksheet shows {case.worksheet_mod}"
    elif kind == "missing_credit":
        case.schedule_credit_applied = False
        desc = f"Promised {case.schedule_credit_pct * 100:.0f}% schedule credit not applied"
    elif kind == "duplicate_class":
        src = case.lines[0]
        case.lines.append(Line(src.state, src.code, src.description, src.payroll, src.rate))
        desc = f"Class {src.code} payroll counted twice"
    elif kind == "overtime_included":
        i = max(range(len(case.lines)), key=lambda k: case.lines[k].payroll)
        case.lines[i].payroll += case.overtime_premium_pay
        desc = "Overtime premium pay included in audited payroll"
    elif kind == "payroll_mismatch":
        # Period without overtime, so the excess is unambiguous.
        case.payroll_records_total -= case.overtime_premium_pay
        case.overtime_premium_pay = Decimal(0)
        i = rng.randrange(len(case.lines))
        pct = Decimal(rng.randrange(2, 10)) / 100  # above the detector's 1% tolerance
        case.lines[i].payroll += q(case.payroll_records_total * pct)
        desc = "Audited payroll exceeds payroll records"
    else:
        raise ValueError(f"unknown error kind: {kind}")
    case.errors.append(InjectedError(kind, desc, case.total_premium - before))


def _fmt(v: Decimal) -> str:
    return f"{v:,.2f}"


def render_pdf(case: SyntheticCase) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, 760, BANNER)
    c.setFont("Helvetica-Bold", 13)
    title = {
        "statement": "PREMIUM AUDIT STATEMENT",
        "worksheet": "FINAL AUDIT WORKSHEET",
        "billing": "AUDIT BILLING - PREMIUM ADJUSTMENT",
    }[case.template]
    c.drawString(40, 735, title)
    c.setFont("Helvetica", 10)
    y = 712
    header = [
        f"Carrier: {case.carrier}",
        f"Insured: {case.employer_name}",
        f"Policy Number: {case.policy_number}",
        f"Policy Period: {case.period_start:%m/%d/%Y} to {case.period_end:%m/%d/%Y}",
        f"State: {case.state}   Audit Type: Final",
    ]
    for text_line in header:
        c.drawString(40, y, text_line)
        y -= 15
    y -= 10
    if case.template == "worksheet":
        for i, ln in enumerate(case.lines):
            c.drawString(40, y, f"Class Code: {ln.code}  {ln.description}  State: {ln.state}")
            y -= 14
            c.drawString(
                60,
                y,
                f"Payroll: {_fmt(ln.payroll)}   Rate: {ln.rate}   "
                f"Premium: {_fmt(case.line_premium(i))}",
            )
            y -= 20
    else:
        cols = (
            ["State", "Class", "Description", "Payroll", "Rate", "Premium"]
            if case.template == "statement"
            else ["Class", "Exposure", "Rate", "Premium", "State", "Description"]
        )
        xs = (
            [40, 85, 135, 330, 420, 480]
            if case.template == "statement"
            else [40, 95, 190, 250, 340, 380]
        )
        c.setFont("Helvetica-Bold", 10)
        for x, col in zip(xs, cols, strict=True):
            c.drawString(x, y, col)
        c.setFont("Helvetica", 10)
        y -= 16
        for i, ln in enumerate(case.lines):
            vals = {
                "State": ln.state,
                "Class": ln.code,
                "Description": ln.description,
                "Payroll": _fmt(ln.payroll),
                "Exposure": _fmt(ln.payroll),
                "Rate": str(ln.rate),
                "Premium": _fmt(case.line_premium(i)),
            }
            for x, col in zip(xs, cols, strict=True):
                c.drawString(x, y, vals[col])
            y -= 15
    y -= 10
    totals = [
        ("Total Manual Premium", case.manual_premium),
        ("Experience Modification", None),
        ("Schedule Credit", None),
        ("Expense Constant", case.expense_constant),
        ("Total Audited Premium", case.total_premium),
        ("Previously Billed", case.previously_billed),
    ]
    for label, value in totals:
        if label == "Experience Modification":
            c.drawString(40, y, f"Experience Modification: {case.mod}")
        elif label == "Schedule Credit":
            if not case.schedule_credit_applied:
                continue
            c.drawString(40, y, f"Schedule Credit: {_fmt(case.schedule_amount)}")
        else:
            assert value is not None
            c.drawString(40, y, f"{label}: {_fmt(value)}")
        y -= 15
    label = "Additional Premium Due" if case.balance >= 0 else "Return Premium"
    c.drawString(40, y, f"{label}: {_fmt(case.balance)}")
    c.showPage()
    c.save()
    return buf.getvalue()


def degrade_to_scan(pdf: bytes, seed: int, dpi: int = 150) -> bytes:
    """Simulate a scan: rasterize, slight rotation, speckle noise, JPEG artifacts; no text layer."""
    import pypdfium2 as pdfium  # noqa: PLC0415
    from PIL import Image, ImageFilter  # noqa: PLC0415

    rng = random.Random(seed)
    doc = pdfium.PdfDocument(pdf)
    try:
        img = doc[0].render(scale=dpi / 72).to_pil().convert("L")
    finally:
        doc.close()
    img = img.rotate(
        rng.uniform(-1.5, 1.5), expand=True, fillcolor=255, resample=Image.Resampling.BICUBIC
    )
    px = img.load()
    assert px is not None
    for _ in range(img.width * img.height // 400):
        x, y = rng.randrange(img.width), rng.randrange(img.height)
        px[x, y] = rng.choice((0, 90, 160))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    jpg = io.BytesIO()
    img.save(jpg, format="JPEG", quality=55)
    out = io.BytesIO()
    Image.open(jpg).save(out, format="PDF", resolution=dpi)
    return out.getvalue()


def corpus(n: int, seed: int = 1000) -> list[SyntheticCase]:
    """Deterministic evaluation corpus: ~half clean, half with 1-2 injected errors."""
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        k = rng.choice([0, 0, 1, 1, 2])
        errs = tuple(rng.sample(ERROR_KINDS, k))
        if {"overtime_included", "payroll_mismatch"} <= set(errs):
            errs = tuple(e for e in errs if e != "payroll_mismatch")
        cases.append(generate_case(seed + i, errs, TEMPLATES[i % len(TEMPLATES)]))
    return cases

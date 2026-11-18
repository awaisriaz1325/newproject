from __future__ import annotations

import io
import zipfile
from collections.abc import Callable

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_pdf(lines: list[str], pages: int = 1, encrypt: str | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, encrypt=encrypt)
    for _ in range(pages):
        y = 720
        for line in lines:
            c.drawString(72, y, line)
            y -= 20
        c.showPage()
    c.save()
    return buf.getvalue()


def make_text_image(lines: list[str], size: tuple[int, int] = (1700, 500)) -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    try:
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.truetype(FONT_PATH, 40)
    except OSError:
        font = ImageFont.load_default(40)
    for i, line in enumerate(lines):
        draw.text((50, 60 + i * 110), line, fill="black", font=font)
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_xlsx(extra: dict[str, bytes] | None = None, cells: list[list[str]] | None = None) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in cells or [["Employee", "SSN", "Wages"], ["A. Smith", "123-45-6789", "1000"]]:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    if not extra:
        return buf.getvalue()
    out = io.BytesIO()
    with zipfile.ZipFile(buf) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        for name, data in extra.items():
            dst.writestr(name, data)
    return out.getvalue()


@pytest.fixture
def pdf_factory() -> Callable[..., bytes]:
    return make_pdf


@pytest.fixture
def image_factory() -> Callable[..., Image.Image]:
    return make_text_image


@pytest.fixture
def to_png() -> Callable[[Image.Image], bytes]:
    return png_bytes


@pytest.fixture
def xlsx_factory() -> Callable[..., bytes]:
    return make_xlsx

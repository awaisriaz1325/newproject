"""Page processing: native text + OCR redaction, pixel black-out, hostile inputs."""

from __future__ import annotations

import io
from collections.abc import Callable

import pytest
from PIL import Image

from compback_vault.filesafety import UnsafeFileError
from compback_vault.pages import process_document, tesseract_available
from compback_vault.redaction import MASK

needs_ocr = pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")


def _dark_fraction(png: bytes) -> float:
    img = Image.open(io.BytesIO(png)).convert("L")
    hist = img.histogram()
    return sum(hist[:20]) / (img.width * img.height)


@needs_ocr
def test_pdf_native_text_redacted_and_blacked_out(pdf_factory: Callable[..., bytes]) -> None:
    clean = process_document(pdf_factory(["Payroll register", "Wages 5,000.00"]), "pdf")
    dirty = process_document(
        pdf_factory(["Payroll register SSN 123-45-6789", "Wages 5,000.00"]), "pdf"
    )
    page = dirty.pages[0]
    assert page.text_source == "native"
    assert "123-45-6789" not in page.text
    assert MASK in page.text
    assert page.redactions.get("ssn_formatted") == 1
    assert page.image_png is not None
    assert clean.pages[0].image_png is not None
    assert _dark_fraction(page.image_png) > _dark_fraction(clean.pages[0].image_png) + 0.0005


@needs_ocr
def test_scanned_image_ocr_redaction(
    image_factory: Callable[..., Image.Image], to_png: Callable[[Image.Image], bytes]
) -> None:
    img = image_factory(["Employee J. Smith SSN 987-65-4320", "Wages 41,250.00 class 8810"])
    result = process_document(to_png(img), "png")
    page = result.pages[0]
    assert page.text_source == "ocr"
    assert "987-65-4320" not in page.text
    assert "8810" in page.text  # non-identifier content preserved
    assert page.ocr_confidence is not None
    assert page.ocr_confidence > 60
    assert page.image_png is not None
    redacted_ocr = process_document(page.image_png, "png").pages[0]
    assert "987" not in redacted_ocr.text  # pixels really gone, not just text


@needs_ocr
def test_scanned_pdf_without_text_layer(image_factory: Callable[..., Image.Image]) -> None:
    img = image_factory(["SSN 123-45-6789 payroll 2,000.00"])
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    page = process_document(buf.getvalue(), "pdf").pages[0]
    assert page.text_source == "ocr"
    assert "123-45-6789" not in page.text


def test_password_protected_pdf_asks_user(pdf_factory: Callable[..., bytes]) -> None:
    with pytest.raises(UnsafeFileError) as info:
        process_document(pdf_factory(["secret"], encrypt="pw"), "pdf")
    assert info.value.code == "pdf_password"
    assert "remove the password" in info.value.user_message


def test_page_limit(pdf_factory: Callable[..., bytes]) -> None:
    with pytest.raises(UnsafeFileError) as info:
        process_document(pdf_factory(["x"], pages=5), "pdf", max_pages=3)
    assert info.value.code == "too_many_pages"


def test_decompression_bomb_image() -> None:
    buf = io.BytesIO()
    Image.new("1", (8000, 8000)).save(buf, format="PNG")  # tiny file, 64M pixels
    assert len(buf.getvalue()) < 200_000
    with pytest.raises(UnsafeFileError) as info:
        process_document(buf.getvalue(), "png")
    assert info.value.code == "image_too_large"


def test_corrupt_pdf() -> None:
    with pytest.raises(UnsafeFileError) as info:
        process_document(b"%PDF-1.4\ngarbage\n%%EOF", "pdf")
    assert info.value.code == "pdf_invalid"


def test_csv_with_ssn_column() -> None:
    data = b"Employee,SSN,Wages\nA. Smith,123-45-6789,1000\nB. Jones,987654321,2000\n"
    page = process_document(data, "csv").pages[0]
    assert "123-45-6789" not in page.text
    assert "987654321" not in page.text
    assert page.redactions == {"tin_table": 2}


def test_xlsx_redaction(xlsx_factory: Callable[..., bytes]) -> None:
    page = process_document(xlsx_factory(), "xlsx").pages[0]
    assert "123-45-6789" not in page.text

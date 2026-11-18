"""Turn an uploaded file into redacted pages: text + a rendered PNG with identifiers blacked out.

Runs on untrusted input — call through ``sandbox.run_isolated`` in the worker.

For PDFs, both the native text layer *and* local OCR of the rendered page are scanned for
identifiers, so an SSN inside an embedded scan is also caught. Nothing in this module talks to the
network; OCR is the local ``tesseract`` binary.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
from dataclasses import dataclass, field
from statistics import mean

from PIL import Image, ImageDraw

from compback_vault.filesafety import FileKind, UnsafeFileError
from compback_vault.redaction import find_spans, redact_table, redact_text

RENDER_DPI = 150
MAX_PIXELS = 25_000_000
NATIVE_TEXT_MIN_CHARS = 20
OCR_TIMEOUT_S = 60
MIN_OCR_CONFIDENCE = 45.0  # below this a scanned page is flagged as low quality
PAD = 3


@dataclass
class PageResult:
    page_no: int
    text: str
    text_source: str  # native | ocr | table
    ocr_confidence: float | None
    redactions: dict[str, int]
    image_png: bytes | None
    width: int | None
    height: int | None
    quality_flags: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    page_count: int
    pages: list[PageResult]

    @property
    def redaction_count(self) -> int:
        return sum(sum(p.redactions.values()) for p in self.pages)


@dataclass(frozen=True)
class OcrWord:
    text: str
    box: tuple[int, int, int, int]  # left, top, right, bottom (pixels)
    conf: float
    line_key: tuple[int, int, int]


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_words(image: Image.Image) -> list[OcrWord]:
    if not tesseract_available():
        raise RuntimeError("tesseract is not installed")
    buf = io.BytesIO()
    image.convert("L").save(buf, format="PNG")
    proc = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "3", "tsv"],  # noqa: S607
        input=buf.getvalue(),
        capture_output=True,
        timeout=OCR_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("OCR failed")
    words: list[OcrWord] = []
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) != 12 or cols[0] != "5" or not cols[11].strip():
            continue
        left, top, width, height = (int(c) for c in cols[6:10])
        words.append(
            OcrWord(
                text=cols[11],
                box=(left, top, left + width, top + height),
                conf=float(cols[10]),
                line_key=(int(cols[2]), int(cols[3]), int(cols[4])),
            )
        )
    return words


def _ocr_lines(words: list[OcrWord]) -> list[tuple[str, list[tuple[int, int, OcrWord]]]]:
    """Group words into lines; return line text with (start, end, word) offsets."""
    lines: dict[tuple[int, int, int], list[OcrWord]] = {}
    for w in words:
        lines.setdefault(w.line_key, []).append(w)
    out = []
    for key in sorted(lines):
        offsets, parts, pos = [], [], 0
        for w in lines[key]:
            offsets.append((pos, pos + len(w.text), w))
            parts.append(w.text)
            pos += len(w.text) + 1
        out.append((" ".join(parts), offsets))
    return out


def _ocr_redaction_boxes(words: list[OcrWord]) -> tuple[list[tuple[int, int, int, int]], int]:
    boxes, count = [], 0
    for text, offsets in _ocr_lines(words):
        for span in find_spans(text):
            hit = [w.box for a, b, w in offsets if a < span.end and b > span.start]
            if hit:
                count += 1
                boxes.append(
                    (
                        min(b[0] for b in hit),
                        min(b[1] for b in hit),
                        max(b[2] for b in hit),
                        max(b[3] for b in hit),
                    )
                )
    return boxes, count


def _black_out(image: Image.Image, boxes: list[tuple[int, int, int, int]]) -> Image.Image:
    if not boxes:
        return image
    img = image.convert("RGB")
    draw = ImageDraw.Draw(img)
    for left, top, right, bottom in boxes:
        draw.rectangle((left - PAD, top - PAD, right + PAD, bottom + PAD), fill="black")
    return img


def _png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _process_image(
    image: Image.Image,
    page_no: int,
    native_text: str | None,
    native_boxes: list[tuple[int, int, int, int]],
    native_count: int,
) -> PageResult:
    words = ocr_words(image)
    ocr_boxes, ocr_count = _ocr_redaction_boxes(words)
    confidences = [w.conf for w in words if w.conf >= 0]
    conf = round(mean(confidences), 1) if confidences else 0.0
    use_native = native_text is not None and len(native_text.strip()) >= NATIVE_TEXT_MIN_CHARS
    if use_native:
        assert native_text is not None
        red = redact_text(native_text)
        text, source = red.text, "native"
        summary = red.summary()
        if ocr_count:
            summary["image_region"] = ocr_count
    else:
        lines = [t for t, _ in _ocr_lines(words)]
        red = redact_text("\n".join(lines))
        text, source, summary = red.text, "ocr", red.summary()
    flags = []
    if source == "ocr" and conf < MIN_OCR_CONFIDENCE:
        flags.append("low_ocr_confidence")
    if source == "ocr" and not text.strip():
        flags.append("no_text_found")
    redacted = _black_out(image, native_boxes + ocr_boxes)
    return PageResult(
        page_no=page_no,
        text=text,
        text_source=source,
        ocr_confidence=None if source == "native" else conf,
        redactions=summary,
        image_png=_png(redacted),
        width=redacted.width,
        height=redacted.height,
        quality_flags=flags,
    )


def _process_pdf(data: bytes, max_pages: int) -> DocumentResult:
    import pypdfium2 as pdfium  # noqa: PLC0415 - heavy native lib, only in the sandbox

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise UnsafeFileError(
                "pdf_password",
                "This PDF is password-protected. Please remove the password and upload again.",
            ) from exc
        raise UnsafeFileError("pdf_invalid", "The PDF could not be read.") from exc
    try:
        n = len(pdf)
        if n == 0:
            raise UnsafeFileError("pdf_empty", "The PDF has no pages.")
        if n > max_pages:
            raise UnsafeFileError("too_many_pages", f"PDFs are limited to {max_pages} pages.")
        pages = []
        for i in range(n):
            page = pdf[i]
            width_pt, height_pt = page.get_size()
            scale = RENDER_DPI / 72
            if width_pt * height_pt * scale * scale > MAX_PIXELS:
                scale = (MAX_PIXELS / (width_pt * height_pt)) ** 0.5
            textpage = page.get_textpage()
            native = textpage.get_text_range()
            boxes, count = [], 0
            for span in find_spans(native):
                rects = [textpage.get_charbox(j) for j in range(span.start, span.end)]
                left = min(r[0] for r in rects)
                right = max(r[2] for r in rects)
                bottom = min(r[1] for r in rects)
                top = max(r[3] for r in rects)
                boxes.append(
                    (
                        int(left * scale),
                        int((height_pt - top) * scale),
                        int(right * scale) + 1,
                        int((height_pt - bottom) * scale) + 1,
                    )
                )
                count += 1
            image = page.render(scale=scale).to_pil()
            pages.append(_process_image(image, i + 1, native, boxes, count))
        return DocumentResult(page_count=n, pages=pages)
    finally:
        pdf.close()


def _process_raster(data: bytes) -> DocumentResult:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Image.DecompressionBombError as exc:
        raise UnsafeFileError("image_too_large", "The image resolution is too large.") from exc
    except Exception as exc:
        raise UnsafeFileError("image_invalid", "The image could not be read.") from exc
    return DocumentResult(page_count=1, pages=[_process_image(image, 1, None, [], 0)])


def _table_result(rows: list[list[str]]) -> DocumentResult:
    redacted, count = redact_table(rows)
    text = "\n".join("\t".join(r) for r in redacted)
    summary = {"tin_table": count} if count else {}
    return DocumentResult(
        page_count=1,
        pages=[
            PageResult(
                page_no=1,
                text=text,
                text_source="table",
                ocr_confidence=None,
                redactions=summary,
                image_png=None,
                width=None,
                height=None,
            )
        ],
    )


def _process_csv(data: bytes) -> DocumentResult:
    text = data.decode("utf-8-sig", errors="replace")
    return _table_result([list(r) for r in csv.reader(io.StringIO(text))])


def _process_xlsx(data: bytes) -> DocumentResult:
    from openpyxl import load_workbook  # noqa: PLC0415 - uses defusedxml when installed

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows: list[list[str]] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else str(v) for v in row])
    wb.close()
    return _table_result(rows)


def process_document(data: bytes, kind: str, max_pages: int = 300) -> DocumentResult:
    match FileKind(kind):
        case FileKind.PDF:
            return _process_pdf(data, max_pages)
        case FileKind.PNG | FileKind.JPEG:
            return _process_raster(data)
        case FileKind.CSV:
            return _process_csv(data)
        case FileKind.XLSX:
            return _process_xlsx(data)

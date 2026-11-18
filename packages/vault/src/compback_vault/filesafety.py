"""Upload safety: allow-listed types by magic bytes, size limits, archive/decompression-bomb checks.

Everything here runs on untrusted bytes. Checks are cheap and conservative; heavy parsing (PDF
rendering, OCR) happens later in a resource-limited subprocess (see ``sandbox``).
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum


class FileKind(StrEnum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    CSV = "csv"
    XLSX = "xlsx"


CONTENT_TYPES = {
    FileKind.PDF: "application/pdf",
    FileKind.PNG: "image/png",
    FileKind.JPEG: "image/jpeg",
    FileKind.CSV: "text/csv",
    FileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSIONS = {
    ".pdf": FileKind.PDF,
    ".png": FileKind.PNG,
    ".jpg": FileKind.JPEG,
    ".jpeg": FileKind.JPEG,
    ".csv": FileKind.CSV,
    ".xlsx": FileKind.XLSX,
}

XLSX_MAX_UNCOMPRESSED = 100 * 1024 * 1024
XLSX_MAX_RATIO = 100
XLSX_MAX_ENTRIES = 2000
CSV_MAX_BYTES = 20 * 1024 * 1024


class UnsafeFileError(ValueError):
    """The file is rejected. ``user_message`` is safe to show to the uploader."""

    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(f"{code}: {user_message}")
        self.code = code
        self.user_message = user_message

    def __reduce__(self) -> tuple[type[UnsafeFileError], tuple[str, str]]:
        # Must survive pickling across the sandbox process boundary.
        return (type(self), (self.code, self.user_message))


@dataclass(frozen=True)
class SafetyResult:
    kind: FileKind
    content_type: str


def sniff(data: bytes) -> FileKind | None:
    head = data[:16]
    if head.startswith(b"%PDF-"):
        return FileKind.PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileKind.PNG
    if head.startswith(b"\xff\xd8\xff"):
        return FileKind.JPEG
    if head.startswith(b"PK\x03\x04"):
        return FileKind.XLSX  # confirmed by structure check below
    if _looks_like_csv(data):
        return FileKind.CSV
    return None


def _looks_like_csv(data: bytes) -> bool:
    sample = data[:65536]
    if not sample or b"\x00" in sample:
        return False
    try:
        text = sample.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
    return printable / len(text) > 0.99 and ("," in text or "\t" in text)


def _check_xlsx(data: bytes) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UnsafeFileError("bad_archive", "The spreadsheet file is damaged.") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > XLSX_MAX_ENTRIES:
            raise UnsafeFileError("archive_too_many_entries", "The spreadsheet is too complex.")
        names = {i.filename for i in infos}
        if "[Content_Types].xml" not in names or not any(n.startswith("xl/") for n in names):
            raise UnsafeFileError("not_xlsx", "Only .xlsx Excel workbooks are supported.")
        total = 0
        for info in infos:
            name = info.filename
            if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                raise UnsafeFileError("archive_path", "The spreadsheet file is malformed.")
            if name.lower().endswith((".bin", ".exe", ".dll")) or "vbaProject" in name:
                raise UnsafeFileError(
                    "macro",
                    "Workbooks with macros or embedded programs "
                    "are not accepted. Save as a plain .xlsx.",
                )
            total += info.file_size
            if info.compress_size and info.file_size / info.compress_size > XLSX_MAX_RATIO:
                raise UnsafeFileError("decompression_bomb", "The spreadsheet looks unsafe.")
        if total > XLSX_MAX_UNCOMPRESSED:
            raise UnsafeFileError("decompression_bomb", "The spreadsheet is too large.")


def check_upload(data: bytes, filename: str, max_bytes: int) -> SafetyResult:
    if not data:
        raise UnsafeFileError("empty", "The file is empty.")
    if len(data) > max_bytes:
        raise UnsafeFileError("too_large", f"Files must be under {max_bytes // (1024 * 1024)} MB.")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    declared = EXTENSIONS.get(ext)
    if declared is None:
        raise UnsafeFileError("type_not_allowed", "Upload PDF, PNG, JPG, CSV or XLSX files only.")
    detected = sniff(data)
    if detected is None or detected != declared:
        raise UnsafeFileError("type_mismatch", "The file contents do not match its extension.")
    if detected == FileKind.XLSX:
        _check_xlsx(data)
    if detected == FileKind.CSV and len(data) > CSV_MAX_BYTES:
        raise UnsafeFileError("too_large", "CSV files must be under 20 MB.")
    if detected == FileKind.PDF and b"%%EOF" not in data[-2048:]:
        raise UnsafeFileError("pdf_truncated", "The PDF looks incomplete. Please upload it again.")
    return SafetyResult(kind=detected, content_type=CONTENT_TYPES[detected])

"""Malicious / malformed file suite for the upload gate."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from compback_vault.filesafety import FileKind, UnsafeFileError, check_upload

MAX = 5 * 1024 * 1024


def _code(data: bytes, name: str) -> str:
    with pytest.raises(UnsafeFileError) as info:
        check_upload(data, name, MAX)
    return info.value.code


def test_accepts_valid_pdf(pdf_factory: Callable[..., bytes]) -> None:
    assert check_upload(pdf_factory(["hello"]), "audit.pdf", MAX).kind == FileKind.PDF


@pytest.mark.parametrize(
    ("data", "name", "code"),
    [
        (b"", "a.pdf", "empty"),
        (b"MZ\x90\x00" + b"\x00" * 100, "invoice.pdf", "type_mismatch"),  # Windows exe renamed
        (b"\x7fELF" + b"\x00" * 100, "audit.png", "type_mismatch"),
        (b"%PDF-1.7\n...", "a.exe", "type_not_allowed"),
        (b"<html><script>alert(1)</script></html>", "a.html", "type_not_allowed"),
        (b"%PDF-1.4\n1 0 obj\n", "truncated.pdf", "pdf_truncated"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, "a.jpg", "type_mismatch"),
        (b"no extension", "README", "type_not_allowed"),
        (b"PK\x03\x04garbage", "book.xlsx", "bad_archive"),
        (b"a,b\n\x00\x01\x02", "data.csv", "type_mismatch"),
    ],
)
def test_rejections(data: bytes, name: str, code: str) -> None:
    assert _code(data, name) == code


def test_too_large() -> None:
    assert _code(b"%PDF-" + b"0" * (MAX + 1), "big.pdf") == "too_large"


def test_xlsx_valid(xlsx_factory: Callable[..., bytes]) -> None:
    assert check_upload(xlsx_factory(), "payroll.xlsx", MAX).kind == FileKind.XLSX


def test_xlsx_with_macro_rejected(xlsx_factory: Callable[..., bytes]) -> None:
    data = xlsx_factory({"xl/vbaProject.bin": b"\x00" * 64})
    assert _code(data, "payroll.xlsx") == "macro"


def test_xlsx_zip_bomb_rejected(xlsx_factory: Callable[..., bytes]) -> None:
    data = xlsx_factory({"xl/bomb.xml": b"0" * (20 * 1024 * 1024)})
    assert _code(data, "payroll.xlsx") == "decompression_bomb"


def test_xlsx_path_traversal_rejected(xlsx_factory: Callable[..., bytes]) -> None:
    data = xlsx_factory({"../../etc/evil.xml": b"x"})
    assert _code(data, "payroll.xlsx") == "archive_path"


def test_plain_zip_is_not_xlsx() -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    assert _code(buf.getvalue(), "file.xlsx") == "not_xlsx"

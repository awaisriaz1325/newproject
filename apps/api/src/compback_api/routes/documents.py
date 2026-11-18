"""Document upload, listing, redacted page viewing, watermarked download, and deletion."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import time
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from PIL import Image, ImageDraw
from pydantic import BaseModel
from sqlalchemy import select

from compback_api.deps import CurrentOrg, OrgAccess, OrgDb, require_owner, utcnow
from compback_core import audit
from compback_core.config import get_settings
from compback_core.models import Document, DocumentPage
from compback_vault.filesafety import UnsafeFileError
from compback_vault.service import Vault

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])
DOWNLOAD_TTL_S = 120


class PageOut(BaseModel):
    page_no: int
    text_source: str
    ocr_confidence: str | None
    redactions: dict[str, int]
    quality_flags: list[str]
    has_image: bool


class DocumentOut(BaseModel):
    id: str
    original_filename: str
    doc_type: str
    file_kind: str
    size_bytes: int
    status: str
    malware_status: str
    page_count: int | None
    redaction_count: int | None
    rejection_message: str | None
    quality_flags: list[str]
    created_at: datetime
    duplicate: bool = False


class DocumentDetailOut(DocumentOut):
    pages: list[PageOut]


class PageTextOut(BaseModel):
    page_no: int
    text: str


class DownloadLinkOut(BaseModel):
    url: str
    expires_in: int


def _out(doc: Document, duplicate: bool = False) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        original_filename=doc.original_filename,
        doc_type=doc.doc_type,
        file_kind=doc.file_kind,
        size_bytes=doc.size_bytes,
        status=doc.status,
        malware_status=doc.malware_status,
        page_count=doc.page_count,
        redaction_count=doc.redaction_count,
        rejection_message=doc.rejection_message,
        quality_flags=doc.quality_flags,
        created_at=doc.created_at,
        duplicate=duplicate,
    )


def _require_writer(access: OrgAccess) -> None:
    if access.access not in ("member", "advisor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "read-only access")
    if not access.principal.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")


def _get_doc(db: OrgDb, access: OrgAccess, doc_id: uuid.UUID) -> Document:
    doc = db.scalar(select(Document).where(Document.id == doc_id, Document.org_id == access.org_id))
    if doc is None or doc.status == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return doc


@router.post("", status_code=status.HTTP_201_CREATED)
def upload(
    access: CurrentOrg, db: OrgDb, file: Annotated[UploadFile, File()], response: Response
) -> DocumentOut:
    _require_writer(access)
    limit = get_settings().max_upload_bytes
    data = file.file.read(limit + 1)
    try:
        doc, duplicate = Vault.from_settings().upload(
            db,
            org_id=access.org_id,
            user_id=access.principal.user_id,
            filename=file.filename or "upload",
            data=data,
            source="advisor" if access.access == "advisor" else "web",
        )
    except UnsafeFileError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"code": exc.code, "message": exc.user_message}
        ) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return _out(doc, duplicate)


@router.get("")
def list_documents(access: CurrentOrg, db: OrgDb) -> list[DocumentOut]:
    docs = db.scalars(
        select(Document)
        .where(Document.org_id == access.org_id, Document.status != "deleted")
        .order_by(Document.created_at.desc())
    )
    return [_out(d) for d in docs]


@router.get("/{doc_id}")
def get_document(doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> DocumentDetailOut:
    doc = _get_doc(db, access, doc_id)
    pages = db.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == doc.id)
        .order_by(DocumentPage.page_no)
    )
    return DocumentDetailOut(
        **_out(doc).model_dump(),
        pages=[
            PageOut(
                page_no=p.page_no,
                text_source=p.text_source,
                ocr_confidence=str(p.ocr_confidence) if p.ocr_confidence else None,
                redactions=p.redactions,
                quality_flags=p.quality_flags,
                has_image=p.image_key is not None,
            )
            for p in pages
        ],
    )


def _get_page(db: OrgDb, doc: Document, page_no: int) -> DocumentPage:
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == doc.id, DocumentPage.page_no == page_no
        )
    )
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return page


def _watermark(png: bytes, label: str) -> Image.Image:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(img)
    step = max(200, img.height // 6)
    for y in range(step // 2, img.height, step):
        draw.text((20, y), label, fill=(200, 200, 200))
    draw.text((20, img.height - 20), label, fill=(120, 120, 120))
    return img


def _label(access: OrgAccess) -> str:
    stamp = utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"CompBack - viewed by {access.principal.email} - {stamp} - redacted copy"


@router.get("/{doc_id}/pages/{page_no}/image")
def page_image(doc_id: uuid.UUID, page_no: int, access: CurrentOrg, db: OrgDb) -> Response:
    doc = _get_doc(db, access, doc_id)
    page = _get_page(db, doc, page_no)
    if page.image_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no image for this page")
    img = _watermark(Vault.from_settings().page_image(page), _label(access))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    audit.record(
        db,
        action="document.viewed",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="document",
        target_id=doc.id,
        details={"page": page_no},
    )
    return Response(
        buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.get("/{doc_id}/pages/{page_no}/text")
def page_text(doc_id: uuid.UUID, page_no: int, access: CurrentOrg, db: OrgDb) -> PageTextOut:
    doc = _get_doc(db, access, doc_id)
    page = _get_page(db, doc, page_no)
    audit.record(
        db,
        action="document.viewed",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="document",
        target_id=doc.id,
        details={"page": page_no, "view": "text"},
    )
    return PageTextOut(page_no=page_no, text=Vault.from_settings().page_text(page))


@lru_cache(maxsize=1)
def _signing_key() -> bytes:
    secret = get_settings().signing_secret
    # Dev/test fallback: per-process random key (config validation forbids this in prod).
    return secret.get_secret_value().encode() if secret else secrets.token_bytes(32)


def _sign(user_id: uuid.UUID, doc_id: uuid.UUID, expires: int) -> str:
    msg = f"{user_id}:{doc_id}:{expires}".encode()
    mac = hmac.new(_signing_key(), msg, hashlib.sha256).digest()
    return f"{expires}.{base64.urlsafe_b64encode(mac).decode().rstrip('=')}"


def _verify(token: str, user_id: uuid.UUID, doc_id: uuid.UUID) -> bool:
    try:
        expires = int(token.split(".", 1)[0])
    except ValueError:
        return False
    return expires >= int(time.time()) and hmac.compare_digest(
        token, _sign(user_id, doc_id, expires)
    )


@router.post("/{doc_id}/download-link")
def download_link(doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> DownloadLinkOut:
    doc = _get_doc(db, access, doc_id)
    token = _sign(access.principal.user_id, doc.id, int(time.time()) + DOWNLOAD_TTL_S)
    return DownloadLinkOut(
        url=f"/orgs/{access.org_id}/documents/{doc.id}/download?token={token}",
        expires_in=DOWNLOAD_TTL_S,
    )


@router.get("/{doc_id}/download")
def download(
    doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb, token: Annotated[str, Query(max_length=200)]
) -> Response:
    """Watermarked PDF of the redacted pages. Needs the session *and* a fresh user-bound token."""
    doc = _get_doc(db, access, doc_id)
    if not _verify(token, access.principal.user_id, doc.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "download link expired or invalid")
    vault = Vault.from_settings()
    pages = [
        p
        for p in db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.page_no)
        )
        if p.image_key
    ]
    if not pages:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no viewable pages")
    label = _label(access).replace("viewed", "downloaded")
    images = [_watermark(vault.page_image(p), label) for p in pages]
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    audit.record(
        db,
        action="document.downloaded",
        org_id=access.org_id,
        actor_user_id=access.principal.user_id,
        actor_kind=access.access,
        target_type="document",
        target_id=doc.id,
    )
    return Response(
        buf.getvalue(),
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="compback-redacted-{doc.id}.pdf"',
        },
    )


@router.delete("/{doc_id}")
def delete_document(doc_id: uuid.UUID, access: CurrentOrg, db: OrgDb) -> DocumentOut:
    require_owner(access)
    doc = _get_doc(db, access, doc_id)
    Vault.from_settings().delete_document(
        db, doc, actor_user_id=access.principal.user_id, reason="owner_request"
    )
    return _out(doc)

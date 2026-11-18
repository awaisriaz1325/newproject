"""Document vault service: store uploads, ingest (scan + redact), read redacted pages, delete."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from compback_core import audit, queue
from compback_core.config import get_settings
from compback_core.logs import get_logger
from compback_core.models import Document, DocumentPage
from compback_vault.crypto import Envelope, get_envelope
from compback_vault.filesafety import UnsafeFileError, check_upload
from compback_vault.malware import Scanner, Verdict, scanner_from_settings
from compback_vault.pages import process_document
from compback_vault.sandbox import SandboxCrashError, SandboxTimeoutError, run_isolated
from compback_vault.storage import ObjectStore, store_from_settings

log = get_logger(__name__)
INGEST_JOB = "document.ingest"
CLASSIFY_JOB = "document.classify"


def original_key(org_id: uuid.UUID, doc_id: uuid.UUID) -> str:
    return f"orgs/{org_id}/documents/{doc_id}/original"


def page_key(org_id: uuid.UUID, doc_id: uuid.UUID, page_no: int) -> str:
    return f"orgs/{org_id}/documents/{doc_id}/pages/{page_no}.png"


def _ctx_original(org_id: uuid.UUID, doc_id: uuid.UUID) -> str:
    return f"documents.original:{org_id}:{doc_id}"


def _ctx_page_image(org_id: uuid.UUID, doc_id: uuid.UUID, page_no: int) -> str:
    return f"document_pages.image:{org_id}:{doc_id}:{page_no}"


def _ctx_page_text(org_id: uuid.UUID, doc_id: uuid.UUID, page_no: int) -> str:
    return f"document_pages.text:{org_id}:{doc_id}:{page_no}"


@dataclass
class Vault:
    store: ObjectStore
    envelope: Envelope
    scanner: Scanner

    @classmethod
    def from_settings(cls) -> Vault:
        return cls(store_from_settings(), get_envelope(), scanner_from_settings())

    # ------------------------------------------------------------------ upload
    def upload(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        filename: str,
        data: bytes,
        source: str = "web",
    ) -> tuple[Document, bool]:
        """Validate, encrypt, store and enqueue ingestion. Returns (document, is_duplicate)."""
        settings = get_settings()
        safety = check_upload(data, filename, settings.max_upload_bytes)
        digest = hashlib.sha256(data).hexdigest()
        existing = db.scalar(
            select(Document).where(
                Document.org_id == org_id, Document.sha256 == digest, Document.deleted_at.is_(None)
            )
        )
        if existing is not None:
            return existing, True
        doc_id = uuid.uuid4()
        key = original_key(org_id, doc_id)
        self.store.put(key, self.envelope.encrypt(data, _ctx_original(org_id, doc_id)))
        doc = Document(
            id=doc_id,
            org_id=org_id,
            file_kind=safety.kind.value,
            content_type=safety.content_type,
            original_filename=_clean_name(filename),
            size_bytes=len(data),
            sha256=digest,
            storage_key=key,
            uploaded_by=user_id,
            upload_source=source,
            retention_until=datetime.now(UTC) + timedelta(days=settings.document_retention_days),
        )
        db.add(doc)
        db.flush()
        queue.enqueue(
            db,
            org_id=org_id,
            kind=INGEST_JOB,
            payload={"document_id": str(doc_id)},
            idempotency_key=str(doc_id),
        )
        audit.record(
            db,
            action="document.uploaded",
            org_id=org_id,
            actor_user_id=user_id,
            target_type="document",
            target_id=doc_id,
            details={"kind": safety.kind.value, "size": len(data)},
        )
        return doc, False

    # ------------------------------------------------------------------ ingest (worker)
    def ingest(self, db: Session, doc_id: uuid.UUID) -> str:
        """Idempotent. Returns the resulting document status."""
        settings = get_settings()
        doc = db.get(Document, doc_id)
        if doc is None or doc.status in ("ready", "rejected", "deleted") or not doc.storage_key:
            return doc.status if doc else "missing"
        doc.status = "processing"
        data = self.envelope.decrypt(
            self.store.get(doc.storage_key), _ctx_original(doc.org_id, doc.id)
        )
        scan = self.scanner.scan(data)
        if scan.verdict == Verdict.ERROR:
            raise RuntimeError("malware scanner unavailable")  # retryable
        if scan.verdict == Verdict.INFECTED:
            doc.malware_status = "infected"
            self._reject(
                db,
                doc,
                "malware",
                "This file was flagged by our malware scanner and "
                "was deleted. Please upload a clean copy.",
            )
            self.store.delete(doc.storage_key)
            doc.storage_key = None
            return doc.status
        doc.malware_status = "clean"
        try:
            result = run_isolated(process_document, data, doc.file_kind, settings.max_pdf_pages)
        except UnsafeFileError as exc:
            self._reject(db, doc, exc.code, exc.user_message)
            return doc.status
        except (SandboxTimeoutError, SandboxCrashError):
            self._reject(
                db,
                doc,
                "processing_limits",
                "This file could not be processed safely (too large or too complex). "
                "Try splitting it or uploading a cleaner scan.",
            )
            return doc.status
        # Idempotent re-run: replace any pages from a previous partial attempt.
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        flags: set[str] = set()
        for page in result.pages:
            image_key = None
            if page.image_png is not None:
                image_key = page_key(doc.org_id, doc.id, page.page_no)
                self.store.put(
                    image_key,
                    self.envelope.encrypt(
                        page.image_png, _ctx_page_image(doc.org_id, doc.id, page.page_no)
                    ),
                )
            db.add(
                DocumentPage(
                    org_id=doc.org_id,
                    document_id=doc.id,
                    page_no=page.page_no,
                    text_source=page.text_source,
                    text_enc=self.envelope.encrypt_str(
                        page.text, _ctx_page_text(doc.org_id, doc.id, page.page_no)
                    ),
                    ocr_confidence=(
                        Decimal(str(page.ocr_confidence))
                        if page.ocr_confidence is not None
                        else None
                    ),
                    redactions=page.redactions,
                    quality_flags=page.quality_flags,
                    image_key=image_key,
                    width=page.width,
                    height=page.height,
                )
            )
            flags.update(page.quality_flags)
        doc.page_count = result.page_count
        doc.redaction_count = result.redaction_count
        doc.quality_flags = sorted(flags)
        doc.status = "ready"
        doc.processed_at = datetime.now(UTC)
        queue.enqueue(
            db,
            org_id=doc.org_id,
            kind=CLASSIFY_JOB,
            payload={"document_id": str(doc.id)},
            idempotency_key=str(doc.id),
        )
        audit.record(
            db,
            action="document.processed",
            org_id=doc.org_id,
            actor_user_id=None,
            actor_kind="worker",
            target_type="document",
            target_id=doc.id,
            details={
                "pages": result.page_count,
                "redactions": result.redaction_count,
                "flags": sorted(flags),
            },
        )
        return doc.status

    def _reject(self, db: Session, doc: Document, code: str, message: str) -> None:
        doc.status = "rejected"
        doc.rejection_code = code
        doc.rejection_message = message
        doc.processed_at = datetime.now(UTC)
        audit.record(
            db,
            action="document.rejected",
            org_id=doc.org_id,
            actor_user_id=None,
            actor_kind="worker",
            target_type="document",
            target_id=doc.id,
            details={"code": code},
        )

    # ------------------------------------------------------------------ read
    def page_text(self, page: DocumentPage) -> str:
        return self.envelope.decrypt_str(
            page.text_enc, _ctx_page_text(page.org_id, page.document_id, page.page_no)
        )

    def page_image(self, page: DocumentPage) -> bytes:
        if page.image_key is None:
            raise FileNotFoundError("page has no image")
        return self.envelope.decrypt(
            self.store.get(page.image_key),
            _ctx_page_image(page.org_id, page.document_id, page.page_no),
        )

    # ------------------------------------------------------------------ delete
    def delete_document(
        self, db: Session, doc: Document, *, actor_user_id: uuid.UUID | None, reason: str
    ) -> None:
        """Hard-delete content (original, page images, derived text); keep a content-free tombstone.

        Backups follow the documented backup retention window (runbook: data deletion request).
        """
        pages = list(db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc.id)))
        for page in pages:
            if page.image_key:
                self.store.delete(page.image_key)
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        if doc.storage_key:
            self.store.delete(doc.storage_key)
        doc.storage_key = None
        doc.sha256 = None
        doc.original_filename = "[deleted]"
        doc.status = "deleted"
        doc.deleted_at = datetime.now(UTC)
        audit.record(
            db,
            action="document.deleted",
            org_id=doc.org_id,
            actor_user_id=actor_user_id,
            actor_kind="user" if actor_user_id else "worker",
            target_type="document",
            target_id=doc.id,
            reason=reason,
        )

    def purge_expired(self, db: Session, now: datetime | None = None) -> int:
        """Retention sweep (worker actor): delete documents past ``retention_until``."""
        now = now or datetime.now(UTC)
        expired = list(
            db.scalars(
                select(Document)
                .where(Document.retention_until <= now, Document.deleted_at.is_(None))
                .limit(500)
            )
        )
        for doc in expired:
            self.delete_document(db, doc, actor_user_id=None, reason="retention_expired")
        return len(expired)


def _clean_name(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    return cleaned[:255] or "upload"

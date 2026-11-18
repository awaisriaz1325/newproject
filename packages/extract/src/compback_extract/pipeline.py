"""Classification + structured extraction for a processed (redacted) document."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from compback_core import audit, queue
from compback_core.config import get_settings
from compback_core.models import Document, DocumentPage, Extraction
from compback_extract.classify import classify_text
from compback_extract.crosscheck import check_premium_audit
from compback_extract.llm import (
    ExtractionRefusedError,
    Extractor,
    HeuristicExtractor,
    MalformedOutputError,
    PageInput,
    Usage,
    extractor_from_settings,
)
from compback_extract.schemas import SCHEMA_VERSION, SCHEMAS, Fld, PremiumAuditV1
from compback_vault.service import Vault

EXTRACT_JOB = "document.extract"
AUTO_READY_CONFIDENCE = 0.9


def _pages(db: Session, vault: Vault, doc: Document, images: bool) -> list[PageInput]:
    rows = db.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == doc.id)
        .order_by(DocumentPage.page_no)
    )
    return [
        PageInput(
            r.page_no, vault.page_text(r), vault.page_image(r) if images and r.image_key else None
        )
        for r in rows
    ]


def classify(db: Session, document_id: uuid.UUID, vault: Vault | None = None) -> str:
    vault = vault or Vault.from_settings()
    doc = db.get(Document, document_id)
    if doc is None or doc.status != "ready":
        return "skipped"
    text = "\n".join(p.text for p in _pages(db, vault, doc, images=False))
    result = classify_text(text)
    doc.doc_type = result.doc_type
    flags = set(doc.quality_flags) | {f"decline:{r}" for r in result.decline_reasons}
    doc.quality_flags = sorted(flags)
    audit.record(
        db,
        action="document.classified",
        org_id=doc.org_id,
        actor_user_id=None,
        actor_kind="worker",
        target_type="document",
        target_id=doc.id,
        details={
            "doc_type": result.doc_type,
            "confidence": result.confidence,
            "declines": result.decline_reasons,
        },
    )
    if result.doc_type in SCHEMAS:
        queue.enqueue(
            db,
            org_id=doc.org_id,
            kind=EXTRACT_JOB,
            payload={"document_id": str(doc.id)},
            idempotency_key=str(doc.id),
        )
    return result.doc_type


def _min_confidence(data: dict[str, Any]) -> float:
    values: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "confidence" in node and node.get("value", node.get("class_code")) is not None:
                values.append(float(node["confidence"]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return min(values) if values else 0.0


def _org_llm_spend(db: Session, org_id: uuid.UUID) -> Decimal:
    rows = db.scalars(select(Extraction.llm_cost_usd).where(Extraction.org_id == org_id))
    return sum(rows, Decimal(0))


def extract(
    db: Session,
    document_id: uuid.UUID,
    extractor: Extractor | None = None,
    vault: Vault | None = None,
) -> Extraction | None:
    """Run extraction with graceful degradation. Transient provider errors propagate (retry)."""
    vault = vault or Vault.from_settings()
    settings = get_settings()
    doc = db.get(Document, document_id)
    if doc is None or doc.status != "ready" or doc.doc_type not in SCHEMAS:
        return None
    schema: type[BaseModel] = SCHEMAS[doc.doc_type]
    reasons: list[str] = []
    extractor = extractor or extractor_from_settings()
    if (
        not isinstance(extractor, HeuristicExtractor)
        and _org_llm_spend(db, doc.org_id) >= settings.llm_cost_cap_usd_per_analysis
    ):
        extractor, reasons = HeuristicExtractor(), ["llm_cost_cap_reached"]
    pages = _pages(db, vault, doc, images=not isinstance(extractor, HeuristicExtractor))
    usage = Usage(model=extractor.name)
    try:
        result, usage = _with_one_repair(extractor, schema, doc.doc_type, pages)
    except ExtractionRefusedError:
        reasons.append("llm_refused")
        result, usage = HeuristicExtractor().extract(schema, doc.doc_type, pages)
    except MalformedOutputError:
        reasons.append("llm_output_invalid")
        result, usage = HeuristicExtractor().extract(schema, doc.doc_type, pages)
    issues = []
    if isinstance(result, PremiumAuditV1):
        issues = [vars(i) for i in check_premium_audit(result)]
        if not result.class_lines:
            reasons.append("no_class_lines_found")
    data = result.model_dump()
    min_conf = _min_confidence(data)
    if issues:
        reasons.append("arithmetic_inconsistency")
    if min_conf < AUTO_READY_CONFIDENCE:
        reasons.append("low_confidence")
    if any(f.startswith("decline:") for f in doc.quality_flags):
        reasons.append("possible_out_of_scope_arrangement")
    row = Extraction(
        org_id=doc.org_id,
        document_id=doc.id,
        doc_type=doc.doc_type,
        schema_name=schema.__name__,
        schema_version=SCHEMA_VERSION,
        extractor=usage.model,
        data=data,
        issues=issues,
        review_reasons=sorted(set(reasons)),
        status="needs_review" if reasons else "ready",
        min_confidence=Decimal(str(round(min_conf, 3))),
        llm_input_tokens=usage.input_tokens,
        llm_output_tokens=usage.output_tokens,
        llm_cost_usd=usage.cost_usd.quantize(Decimal("0.0001")),
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="document.extracted",
        org_id=doc.org_id,
        actor_user_id=None,
        actor_kind="worker",
        target_type="document",
        target_id=doc.id,
        details={
            "extractor": usage.model,
            "status": row.status,
            "issues": len(issues),
            "cost_usd": str(row.llm_cost_usd),
        },
    )
    return row


def _with_one_repair(
    extractor: Extractor, schema: type[BaseModel], doc_type: str, pages: list[PageInput]
) -> tuple[BaseModel, Usage]:
    try:
        return extractor.extract(schema, doc_type, pages)
    except MalformedOutputError:
        return extractor.extract(schema, doc_type, pages)  # one repair attempt


# ------------------------------------------------------------------ human verification


def _set_path(data: dict[str, Any], path: str, value: str | None) -> str | None:
    """Set e.g. 'total_premium' (an Fld) or 'class_lines[1].payroll'. Returns the old value."""
    node: Any = data
    parts = path.replace("]", "").replace("[", ".").split(".")
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() else node[part]
    last = parts[-1]
    if isinstance(node, dict) and isinstance(node.get(last), dict):  # Fld
        old = node[last].get("value")
        node[last] = Fld(value=value, page=node[last].get("page"), confidence=1.0).model_dump()
        return None if old is None else str(old)
    if isinstance(node, dict) and last in node:
        old = node[last]
        node[last] = value
        if "confidence" in node:
            node["confidence"] = 1.0
        return None if old is None else str(old)
    raise KeyError(path)


def apply_edits(
    row: Extraction, edits: list[tuple[str, str | None]]
) -> list[tuple[str, str | None, str | None]]:
    data = dict(row.data)
    applied = []
    for path, value in edits:
        old = _set_path(data, path, value)
        applied.append((path, old, value))
    schema = SCHEMAS[row.doc_type]
    model = schema.model_validate(data)  # rejects structurally invalid edits
    row.data = model.model_dump()
    if isinstance(model, PremiumAuditV1):
        row.issues = [vars(i) for i in check_premium_audit(model)]
    return applied


def mark_verified(row: Extraction, user_id: uuid.UUID) -> None:
    row.status = "verified"
    row.verified_by = user_id
    row.verified_at = datetime.now(UTC)

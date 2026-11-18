"""Extraction-stage job handlers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from compback_extract import pipeline


def classify_document(db: Session, document_id: uuid.UUID) -> None:
    pipeline.classify(db, document_id)


def extract_document(db: Session, document_id: uuid.UUID) -> None:
    pipeline.extract(db, document_id)

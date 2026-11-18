"""Extraction-stage handlers. Phase 4 replaces the placeholder classifier."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session


def classify_document(db: Session, document_id: uuid.UUID) -> None:
    """Placeholder until Phase 4: leaves ``doc_type = 'unknown'``."""
    del db, document_id

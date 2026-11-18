"""Audit log helpers. The database trigger assigns seq/prev_hash/hash (ADR-0011)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from compback_core.models import AuditLog

GENESIS = "0" * 64


def record(
    session: Session,
    *,
    action: str,
    org_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    actor_kind: str = "user",
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an audit entry in the caller's transaction. Never put PII in ``details``.

    Uses a plain INSERT without RETURNING: the writer may be allowed to append to a chain it is
    not allowed to read back (e.g. auth events), and RLS checks SELECT policies on RETURNING.
    """
    session.flush()
    session.execute(
        insert(AuditLog).values(
            org_id=org_id,
            actor_user_id=actor_user_id,
            actor_kind=actor_kind,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            reason=reason,
            details=details or {},
        )
    )


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    entries: int
    broken_at_seq: int | None = None


def verify_chain(session: Session, org_id: uuid.UUID) -> ChainCheck:
    """Recompute every hash for an org's chain (visible under the caller's RLS context)."""
    rows = session.execute(
        text(
            "SELECT seq, prev_hash, hash, compback.audit_payload(a) AS payload "
            "FROM audit_log a WHERE org_id = :org ORDER BY seq"
        ),
        {"org": org_id},
    ).all()
    prev = GENESIS
    for expected_seq, row in enumerate(rows, start=1):
        computed = hashlib.sha256((prev + row.payload).encode()).hexdigest()
        if row.seq != expected_seq or row.prev_hash != prev or row.hash != computed:
            return ChainCheck(ok=False, entries=len(rows), broken_at_seq=row.seq)
        prev = row.hash
    return ChainCheck(ok=True, entries=len(rows))


def list_entries(session: Session, org_id: uuid.UUID, limit: int = 200) -> list[AuditLog]:
    stmt = (
        select(AuditLog).where(AuditLog.org_id == org_id).order_by(AuditLog.seq.desc()).limit(limit)
    )
    return list(session.scalars(stmt))

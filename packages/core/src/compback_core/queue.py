"""Postgres job queue (ADR-0003): SKIP LOCKED claims, leases, backoff, parking, per-org limits."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from compback_core.models import Job

LEASE_SECONDS = 600
BACKOFF_BASE_SECONDS = 10
BACKOFF_MAX_SECONDS = 3600
PER_ORG_CONCURRENCY = 2


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    org_id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


def enqueue(
    session: Session,
    *,
    org_id: uuid.UUID,
    kind: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 5,
    run_after: datetime | None = None,
) -> None:
    """Insert a job in the caller's transaction. Duplicate idempotency keys are ignored."""
    stmt = (
        insert(Job)
        .values(
            org_id=org_id,
            kind=kind,
            payload=payload or {},
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            run_after=run_after or datetime.now(UTC),
        )
        .on_conflict_do_nothing(
            index_elements=["org_id", "kind", "idempotency_key"],
            index_where=text("idempotency_key IS NOT NULL"),
        )
    )
    session.execute(stmt)


def claim(
    session: Session, kinds: list[str] | None = None, per_org_limit: int = PER_ORG_CONCURRENCY
) -> ClaimedJob | None:
    """Claim one runnable job. Expired leases (crashed workers) are reclaimable.

    The session must run with actor_kind='worker'.
    """
    row = session.execute(
        text(
            """
            WITH candidate AS (
              SELECT j.id FROM jobs j
              WHERE (j.state = 'queued' OR (j.state = 'running' AND j.locked_until < now()))
                AND j.run_after <= now()
                AND (CAST(:kinds AS text[]) IS NULL OR j.kind = ANY(CAST(:kinds AS text[])))
                AND (SELECT count(*) FROM jobs r WHERE r.org_id = j.org_id
                     AND r.state = 'running' AND r.locked_until >= now()) < :limit
              ORDER BY j.run_after
              LIMIT 1
              FOR UPDATE SKIP LOCKED
            )
            UPDATE jobs SET state = 'running', attempts = jobs.attempts + 1,
                   locked_until = now() + make_interval(secs => :lease)
            FROM candidate WHERE jobs.id = candidate.id
            RETURNING jobs.id, jobs.org_id, jobs.kind, jobs.payload, jobs.attempts,
                      jobs.max_attempts
            """
        ),
        {"kinds": kinds, "limit": per_org_limit, "lease": LEASE_SECONDS},
    ).first()
    if row is None:
        return None
    return ClaimedJob(row.id, row.org_id, row.kind, row.payload, row.attempts, row.max_attempts)


def complete(session: Session, job_id: uuid.UUID) -> None:
    session.execute(
        text(
            "UPDATE jobs SET state = 'succeeded', finished_at = now(), locked_until = NULL, "
            "last_error = NULL WHERE id = :id"
        ),
        {"id": job_id},
    )


def backoff_seconds(attempts: int) -> int:
    return int(min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1))))


def fail(session: Session, job: ClaimedJob, error: str, *, retryable: bool = True) -> str:
    """Record a failure: retry with exponential backoff, or park after max attempts."""
    if retryable and job.attempts < job.max_attempts:
        state = "queued"
        run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds(job.attempts))
    else:
        state = "parked" if retryable else "failed"
        run_after = datetime.now(UTC)
    session.execute(
        text(
            "UPDATE jobs SET state = :s, run_after = :r, locked_until = NULL, "
            "last_error = :e, finished_at = :f WHERE id = :id"
        ),
        {
            "s": state,
            "r": run_after,
            "e": error[:2000],
            "f": datetime.now(UTC) if state in ("parked", "failed") else None,
            "id": job.id,
        },
    )
    return state

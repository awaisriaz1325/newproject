"""Job dispatch. Each job runs in its own transaction with the job's org as tenant context.

Claiming is a separate short transaction, so a crash mid-job leaves a lease that expires and the
job is re-claimed (handlers are idempotent).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from compback_core import queue
from compback_core.db import tenant_session
from compback_core.logs import get_logger
from compback_extract.pipeline import EXTRACT_JOB
from compback_vault.service import CLASSIFY_JOB, INGEST_JOB, Vault
from compback_worker.extraction import classify_document, extract_document

log = get_logger(__name__)

Handler = Callable[[Session, queue.ClaimedJob], None]
HANDLERS: dict[str, Handler] = {}


class PermanentJobError(Exception):
    """Do not retry (input is invalid); the job goes straight to 'failed'."""


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


@handler(INGEST_JOB)
def _ingest(db: Session, job: queue.ClaimedJob) -> None:
    Vault.from_settings().ingest(db, uuid.UUID(job.payload["document_id"]))


@handler(CLASSIFY_JOB)
def _classify(db: Session, job: queue.ClaimedJob) -> None:
    classify_document(db, uuid.UUID(job.payload["document_id"]))


@handler(EXTRACT_JOB)
def _extract(db: Session, job: queue.ClaimedJob) -> None:
    extract_document(db, uuid.UUID(job.payload["document_id"]))


def run_once(kinds: list[str] | None = None) -> int:
    with tenant_session(None, None, actor_kind="worker") as db:
        job = queue.claim(db, kinds or sorted(HANDLERS))
    if job is None:
        return 0
    started = time.perf_counter()
    try:
        with tenant_session(job.org_id, None, actor_kind="worker") as db:
            HANDLERS[job.kind](db, job)
            queue.complete(db, job.id)
        log.info(
            "job_succeeded",
            job_id=str(job.id),
            kind=job.kind,
            ms=round((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
        retryable = not isinstance(exc, PermanentJobError)
        with tenant_session(job.org_id, None, actor_kind="worker") as db:
            state = queue.fail(db, job, f"{type(exc).__name__}: {exc}", retryable=retryable)
        log.warning(
            "job_failed",
            job_id=str(job.id),
            kind=job.kind,
            state=state,
            error_type=type(exc).__name__,
        )
    return 1


def run_retention_sweep(now: datetime | None = None) -> int:
    with tenant_session(None, None, actor_kind="worker") as db:
        return Vault.from_settings().purge_expired(db, now or datetime.now(UTC))

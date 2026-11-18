"""Job queue semantics against real Postgres: idempotency, leases, backoff, parking, fairness."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from compback_core import queue
from compback_core.db import tenant_session
from compback_core.models import Organization

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module", autouse=True)
def _migrated() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


def _org() -> uuid.UUID:
    org_id = uuid.uuid4()
    with tenant_session(None, None, actor_kind="system") as db:
        db.add(
            Organization(id=org_id, kind="employer", name="Q", invite_code=uuid.uuid4().hex[:10])
        )
    return org_id


def _claim(kind: str) -> queue.ClaimedJob | None:
    with tenant_session(None, None, actor_kind="worker") as db:
        return queue.claim(db, [kind])


def test_enqueue_is_idempotent() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind, idempotency_key="k1")
        queue.enqueue(db, org_id=org, kind=kind, idempotency_key="k1")
        n = db.execute(text("SELECT count(*) FROM jobs WHERE kind = :k"), {"k": kind}).scalar_one()
    assert n == 1


def test_claim_complete_and_no_double_claim() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind)
    job = _claim(kind)
    assert job is not None
    assert job.attempts == 1
    assert _claim(kind) is None  # leased
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.complete(db, job.id)
    assert _claim(kind) is None


def test_failure_backoff_then_park() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind, max_attempts=2)
    job = _claim(kind)
    assert job is not None
    with tenant_session(org, None, actor_kind="worker") as db:
        assert queue.fail(db, job, "boom") == "queued"
        db.execute(text("UPDATE jobs SET run_after = now() WHERE id = :i"), {"i": job.id})
    job2 = _claim(kind)
    assert job2 is not None
    assert job2.attempts == 2
    with tenant_session(org, None, actor_kind="worker") as db:
        assert queue.fail(db, job2, "boom") == "parked"


def test_permanent_failure_not_retried() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind)
    job = _claim(kind)
    assert job is not None
    with tenant_session(org, None, actor_kind="worker") as db:
        assert queue.fail(db, job, "bad input", retryable=False) == "failed"


def test_expired_lease_is_reclaimed_after_worker_crash() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind)
    job = _claim(kind)
    assert job is not None
    with tenant_session(org, None, actor_kind="worker") as db:  # simulate crash: lease expires
        db.execute(
            text("UPDATE jobs SET locked_until = now() - interval '1 second' WHERE id = :i"),
            {"i": job.id},
        )
    again = _claim(kind)
    assert again is not None
    assert again.id == job.id
    assert again.attempts == 2


def test_per_org_concurrency_limit() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        for _ in range(3):
            queue.enqueue(db, org_id=org, kind=kind)
    claimed = [_claim(kind) for _ in range(3)]
    assert sum(j is not None for j in claimed) == queue.PER_ORG_CONCURRENCY


def test_backoff_grows_and_caps() -> None:
    assert queue.backoff_seconds(1) < queue.backoff_seconds(3) <= queue.BACKOFF_MAX_SECONDS
    assert queue.backoff_seconds(50) == queue.BACKOFF_MAX_SECONDS


def test_future_jobs_wait() -> None:
    org, kind = _org(), f"t.{uuid.uuid4().hex[:6]}"
    with tenant_session(org, None, actor_kind="worker") as db:
        queue.enqueue(db, org_id=org, kind=kind, run_after=datetime.now(UTC) + timedelta(hours=1))
    assert _claim(kind) is None

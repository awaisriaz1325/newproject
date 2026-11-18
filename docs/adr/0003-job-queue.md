# ADR-0003: Postgres-backed job queue (`FOR UPDATE SKIP LOCKED`)

- Status: accepted · Date: 2026-11-18 · Risk: Medium (reliability)

## Context
Document processing is async, needs idempotent retries, per-tenant concurrency limits, and must fit a
$50–200/month budget.

## Decision
A small in-house queue in `packages/core` on a `jobs` table: `SELECT … FOR UPDATE SKIP LOCKED`,
`attempts`, `max_attempts`, exponential backoff via `run_after`, `locked_until` lease for crash
recovery, `idempotency_key` unique per (org, kind), and a `parked` state after max attempts.

## Alternatives
- Redis + Celery/RQ/Dramatiq: extra service and cost, second source of truth.
- Procrastinate (Postgres queue library): good, but adds async-framework coupling; our needs are ~150 LOC
  and fully testable. Revisit if requirements grow (cron, chaining, dashboards).
- SQS: AWS dependency, cost, harder local dev.

## Consequences
Queue and data share one transaction boundary (enqueue in the same transaction as the upload row).
Throughput is far beyond launch needs.

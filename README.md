# CompBack

AI-assisted workers' compensation premium audit review for US employers. CompBack reads a
policyholder's policy and audit documents, **recomputes the premium independently** with a
deterministic Decimal engine, flags likely overcharges with evidence, and prepares a dispute package
that **the business (or its own advisor) reviews and submits**. CompBack never contacts carriers.

> Status: pre-launch. See `docs/FOUNDER_DECISIONS.md` — paid features are disabled in every state
> until counsel review (`docs/phase-0/01-legal-regulatory.md`).

## Repository layout

```
apps/web          Next.js (App Router, TypeScript strict, Tailwind) — customer/advisor/reviewer UI
apps/api          FastAPI HTTP layer
apps/worker       Document pipeline worker (Postgres job queue)
packages/core     Config, logging, DB/tenancy, money, jurisdictions, queue, audit log, models
packages/vault    Encryption, object storage, upload safety, SSN/TIN redaction
packages/extract  OCR/text, versioned extraction schemas, LLM adapter, cross-checks
packages/rating   Premium recomputation engine, rules registry, detectors
packages/ml       Class-code review assistant, finding prioritization, eval harness
packages/disputes Dispute package generation
migrations        Alembic migrations (run as owner role; RLS policies live here)
infra             Dockerfiles, DB bootstrap
docs              ADRs, threat model, Phase 0 research, phase reports, runbooks
tests             Cross-package integration and golden tests
```

## Prerequisites

Python 3.13, [uv](https://docs.astral.sh/uv/), Node 22 + pnpm 10, PostgreSQL 16, and (for the
worker) `tesseract-ocr`. Docker is optional (`docker compose up` runs db, clamav, api, worker, web).

## Quick start (without Docker)

```bash
cp .env.example .env   # then set COMPBACK_LOCAL_MASTER_KEY_B64
```

```bash
PGHOST=localhost PGUSER=postgres infra/db/create_db.sh compback
```

```bash
uv sync && make migrate
```

```bash
uv run uvicorn compback_api.main:app --reload
```

```bash
cd apps/web && pnpm install && pnpm dev
```

## Checks (same commands CI runs)

```bash
PGHOST=localhost PGUSER=postgres infra/db/create_db.sh compback_test
```

```bash
make lint typecheck test migrate-check audit
```

```bash
cd apps/web && pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

## Principles

- Money is `Decimal` / `NUMERIC`, never float (ADR-0008).
- Every tenant table has Postgres RLS **and** an application tenant scope (ADR-0002, Phase 2).
- SSNs never persist; only redacted content reaches an LLM (ADR-0005).
- Every rating rule cites its source; uncited rules are `candidate` only (docs/rules).
- Estimates are ranges labelled "estimated, not guaranteed".

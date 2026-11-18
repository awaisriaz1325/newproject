# ADR-0002: Technology stack

- Status: accepted · Date: 2026-11-18 · Risk: Low

## Decision
| Concern | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript strict + Tailwind CSS + shadcn/ui pattern |
| API | Python 3.13 + FastAPI + Pydantic v2 |
| ORM / migrations | SQLAlchemy 2.0 (typed) + Alembic; RLS policies written in raw SQL in migrations |
| DB | PostgreSQL 16 (managed: Neon in prod) |
| Python tooling | uv, ruff (lint+format), mypy --strict, pytest, hypothesis |
| JS tooling | pnpm, ESLint, `tsc --noEmit`, Vitest, Playwright |
| Containers | Docker / docker compose for local dev |

Exact versions are pinned in lockfiles at install time (checked against the package registries then,
not from memory).

## Consequences
Two languages. Python owns everything that touches money, documents, extraction, and ML; the web app
is a thin client of the API with no direct DB access.

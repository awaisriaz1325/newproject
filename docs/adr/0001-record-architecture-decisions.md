# ADR-0001: Record architecture decisions; monorepo layout

- Status: accepted · Date: 2026-11-18 · Risk: Low

## Context
The build prompt requires ADRs and proposes a monorepo (`apps/*`, `packages/*`).

## Decision
Use ADRs in `docs/adr/NNNN-title.md` (this format: Context / Decision / Consequences / Alternatives).
Adopt the proposed monorepo layout. Python packages live under `packages/` as one **uv workspace**;
the web app is a **pnpm** workspace under `apps/web`.

## Consequences
One `uv.lock` for all Python code, one `pnpm-lock.yaml` for JS. Cross-package imports are explicit
workspace dependencies.

## Alternatives
Polyrepo (rejected: solo founder, shared domain types). Nx/Turborepo (rejected for now: one JS app).

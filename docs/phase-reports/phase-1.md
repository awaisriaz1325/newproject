# Phase 1 report — Repository foundation

**Built**
- uv workspace (8 Python packages) + pnpm Next.js 16 app; `Makefile` targets mirror CI.
- `compback_core`: typed settings with prod-safety validator, PII-scrubbing structlog JSON logging,
  SQLAlchemy engine + transaction-local tenant context (`app.org_id`, `app.user_id`), Decimal money
  helpers that reject floats, declarative base with naming conventions.
- FastAPI app factory with request IDs, security headers, `/healthz`, `/readyz` (503 when DB down).
- Worker entrypoint with graceful shutdown.
- Alembic (owner role) + baseline migration (helper schema, default privileges for app role).
  `make migrate-check` = upgrade → downgrade → upgrade + model-drift detection.
- DB bootstrap: `compback_owner` (owns objects) and `compback_app` (no BYPASSRLS, not owner).
- Docker: shared Python image (non-root, tesseract), web standalone image, compose with ClamAV and a
  sandboxed worker (read-only FS, no caps, memory/pid limits).
- CI (GitHub Actions): lint, mypy strict, migration check, tests with Postgres service, pip-audit,
  web lint/typecheck/test/build, `pnpm audit --prod`, gitleaks. Action versions verified via
  `git ls-remote` on 2026-11-18.
- Pre-commit: hygiene hooks, gitleaks, ruff.

**Check results (local, real output)**
- `ruff check` + `ruff format --check`: pass. `mypy --strict` on 19 files: "Success: no issues found".
- `pytest`: 20 passed, coverage 87%. `migrate-check`: "round-trip passed, no model drift".
- `pip-audit`: "No known vulnerabilities found". `pnpm audit --prod`: "No known vulnerabilities found".
- Web: eslint 0 warnings, `tsc --noEmit` clean, vitest 3 passed, `next build` succeeded.

**Known exception (Low):** `pnpm audit` (including dev deps) reports GHSA-fc5q-39xc-vjpf (picomatch
ReDoS) via vite/eslint tooling, **no patched version published**. Dev-only, not shipped. CI audits
production dependencies; revisit when a patch exists.

**Not verified here:** Docker images were not built (no Docker daemon in this environment); GitHub
Actions will be the first real run.

**Assumptions:** Neon/managed Postgres lets us create two roles equivalent to `bootstrap.sql`.

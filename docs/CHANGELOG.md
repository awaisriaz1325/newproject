# Changelog

All notable changes are recorded here (Keep a Changelog style).

## [Unreleased]

### Phase 0 — 2026-11-18
- Legal/regulatory research, reference-data licensing, provider and cost research.
- ADRs 0001–0012, threat model v0.1, architecture data-flow and ERD, founder decision list.

### Phase 1 — 2026-11-18
- Monorepo (uv workspace + Next.js 16), typed config, PII-safe logging, tenant-context DB sessions,
  money helpers, health checks, Alembic with drift check, Docker/compose, CI, pre-commit.

### Phase 2 — 2026-11-18
- Tenancy, auth (argon2id, sessions, CSRF, TOTP MFA, lockout, rate limits), advisor consent links,
  reviewer JIT grants, RLS on all tenant tables, hash-chained append-only audit log, jurisdiction seed.

### Phase 3 — 2026-11-18
- Secure document vault: upload safety, ClamAV scanning, local OCR + SSN/TIN redaction in text and
  pixels, sandboxed processing, envelope-encrypted storage, watermarked views/downloads with user-bound
  links, retention and hard deletion, Postgres job queue and worker.

### Phase 4 — 2026-11-18
- Extraction schemas, classifier, baseline + Claude extractors, cross-checks, review routing,
  verification API, synthetic corpus generator and evaluation harness with measured results.

### Phase 5 — 2026-11-18
- Rules registry with NCRB citations, Decimal engine with explanations, 7 detectors with engine-priced
  impacts, golden/property tests, policies/recomputations/findings persistence, analysis + reviewer API.

### Phases 6–8 — 2026-11-18
- Class-code review assistant (licensing-gated), prioritization baseline, quality tracking.
- Cases workflow, dispute package PDF/DOCX, deadlines with sources, outcomes with proof, fee
  transparency, Stripe invoicing with idempotency and signed, idempotent webhooks.

### Web UI — 2026-11-18
- Landing page (no invented statistics), signup/sign-in/MFA/verification, workspace with uploads and
  live status, side-by-side extraction verification, free-scan report with citations and line-by-line
  recomputation, case tracker (package download, fee terms, submission record, outcomes, fees),
  customer-visible access log, advisor invite/approve/revoke, legal placeholders.
- Browser smoke test (`tests/e2e/smoke.cjs`) run locally end-to-end.

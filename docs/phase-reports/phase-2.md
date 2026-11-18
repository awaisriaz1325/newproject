# Phase 2 report — Tenancy, auth, RBAC, consent

**Built**
- Models + migration 0002: organizations (employer / advisor_firm / platform), users, memberships
  (owner, member, advisor, reviewer, platform_admin), sessions, email tokens, email outbox, advisor
  client links, consents, access grants (JIT), audit log, rate-limit counters, jobs, jurisdiction policies.
- RLS on every tenant table with a DB-side access function (ADR-0013); append-only, trigger-hash-chained
  audit log (ADR-0011) + Python verifier.
- Migration 0003 seeds 53 jurisdictions: paid analysis/contingency **off everywhere**; ND/OH/WA/WY/PR/VI
  declined; NY/VA/ME/OR/IN/TX notes with citations.
- Auth: signup (no account enumeration) → email verification → login; argon2id; lockout after 10
  failures; opaque session tokens (hash stored), HttpOnly SameSite=Lax cookie, CSRF double-submit;
  TOTP MFA with encrypted secret (envelope encryption, ADR-0010) and single-use hashed recovery codes;
  **MFA mandatory** for advisor firms, advisor/reviewer roles and platform staff; Postgres-backed
  rate limits.
- Advisor flow: advisor firm requests link with employer invite code → employer owner approves
  (consent recorded) → access; either side revokes → access ends immediately (app + RLS).
- Reviewer JIT access: platform staff + MFA + reason (≥10 chars) + expiry ≤ 4 h; logged and visible in
  the customer's access log.
- Endpoints: `/auth/*`, `/orgs/{id}`, advisor links, access grants, `/access-log`, `/audit`,
  `/audit/verify`, `/jurisdictions`.

**Check results (real output)**
- `ruff`: All checks passed. `mypy --strict`: Success, 30 source files.
- `pytest`: **71 passed**, coverage 90%. Includes per-table RLS isolation, spoofed-context, cross-tenant
  insert, no-context, read-only jurisdiction table, and per-endpoint cross-tenant 404 tests.
- `migrate-check`: round-trip passed, no model drift.

**Assumptions / deferred**
- Google sign-in (OIDC) is deferred to Phase 7 polish (FD-08: hosted auth may replace it).
- Email delivery: outbox table only; provider adapter + worker sender land with Phase 7 reminders.
- Password reset flow: token purpose exists; endpoint deferred to Phase 7.

# Threat model (STRIDE) — v1.0 (Phase 9)

> Phase 9 status: T1–T14 and T16 mitigations implemented and covered by tests; T15 documented. Open items below.

Updated every phase. Severity: Low / Medium / High / Critical.

## Assets and data classification

| Class | Examples | Controls |
|---|---|---|
| **Restricted** | FEIN, residual tax ids, payroll by person, refund bank details (not stored in v1), original uploaded documents | Envelope encryption (ADR-0010), JIT access, audit every read, never in logs, never to LLM unredacted |
| **Confidential** | Policy numbers, carrier names, class payroll totals, findings, recomputations, case notes | RLS + app tenant scope, TLS, encrypted at rest (provider) |
| **Internal** | Rules registry, model versions, job metadata, metrics | AuthN required |
| **Public** | Marketing pages, public rule citations | — |
| **Never stored** | SSNs, ITINs, bank account numbers | Redacted at ingest; detectors tested |

## Trust boundaries

1. Browser ↔ web (Next.js) ↔ API (FastAPI) — TLS, session cookie, CSRF.
2. API ↔ Postgres — RLS with `app.org_id` set per transaction; app role is not table owner.
3. Worker ↔ uploaded files — sandboxed process, resource limits, ClamAV, no network except storage/LLM.
4. Worker ↔ LLM provider — redacted content only, schema-validated output.
5. Internal reviewers ↔ customer data — MFA, just-in-time grant with reason, audited.

## Threats

| # | STRIDE | Threat | Sev | Mitigation | Phase |
|---|---|---|---|---|---|
| T1 | I | Cross-tenant data leak via missing `WHERE org_id` | Critical | Postgres RLS (app role is non-owner, ADR-0013) + app scope + automated cross-tenant tests per table/endpoint | 2 |
| T2 | S | Account takeover (credential stuffing) | High | argon2id, rate limit, MFA mandatory for advisors/reviewers, session rotation | 2 |
| T3 | E | Advisor keeps access after consent revoked | High | Access derived from active `advisor_client_links` row at query time; revocation is immediate | 2 |
| T4 | I | Internal reviewer browses customer docs | High | JIT grants with reason + expiry, audit log visible to customer | 2–3 |
| T5 | T | Audit log tampering | Medium | Insert-only grants + trigger + hash chain verifier | 2 |
| T6 | I | SSN stored in derived text / sent to LLM | Critical | Redaction before persistence of derived text; tests on synthetic SSN corpus incl. OCR'd scans | 3–4 |
| T7 | D/E | Malicious file (PDF bomb, zip bomb, polyglot, exploit) | High | Allow-list, magic bytes, size/page caps, ClamAV, sandboxed worker with timeouts/memory caps | 3 |
| T8 | T | Prompt injection in uploaded documents alters findings (red-team suite: test_extract.py) | High | Docs never in instructions; strict schema; engine recomputes all numbers; red-team suite in CI | 4 |
| T9 | I | Signed URL leakage | Medium | 60–300 s expiry, bound to user via API proxy, download watermark, no public buckets | 3 |
| T10 | R | Customer disputes who approved/submitted a package | Medium | Approval + submission recorded with actor, time, method; audit chain | 7 |
| T11 | T | Stripe webhook spoof / replay | High | Signature verification, event-id idempotency table | 8 |
| T12 | I | PII in logs/traces | High | Structured logger with denylist redaction; no request bodies logged | 1 |
| T13 | E | Wrong finding sent → legal/financial harm | High | Reviewer confirmation required; no `candidate` rule affects customer numbers | 5–7 |
| T14 | D | LLM cost runaway / abuse of free scan | Medium | Per-org + global cost caps, rate limits, page caps on free scan | 4, 7 |
| T15 | I | Backup retains deleted customer data | Medium | Documented backup retention window; deletion SLA states it | 10 |
| T16 | S | CSRF on state-changing endpoints | Medium | SameSite=Lax + double-submit token | 2 |

## Open items (Phase 9 review, 2026-11-18)

| Item | Severity | Status / plan |
|---|---|---|
| Web CSP allows `'unsafe-inline'` scripts (Next.js inline runtime) | Medium | Accepted for v1; move to nonce-based CSP via Next proxy before GA |
| Session token not rotated when MFA is verified (only the flag flips) | Medium | Fix: issue a new session on MFA verify; tracked |
| No self-service password reset (token purpose exists) | Low (support load) | Implement with email provider (FD-07) |
| `worker`/`system` actor kinds widen RLS; set only by server code | Medium | Accepted by design (ADR-0013); never derived from request input; reviewed |
| External pen test not done | High (process) | Before launch; budget decision for founder |
| Real ClamAV signature DB not exercised here | Medium | Verify in staging with EICAR upload |
| Rate limits are per-IP fixed windows | Low | Add per-account limits if abuse appears |
| KMS account and key policy | High (until done) | FD-07; prod config refuses to start without it |

# Phases 9–10 report — Hardening, deployment readiness

## Hardening (real runs)
- **Security review** against the threat model (bundled review tool unavailable on this branch; done
  manually). Added rate limits to upload (60/5 min) and analysis (20/5 min) endpoints (build rule §8).
  Open items with severities in `docs/security/threat-model.md`.
- **Backup restore drill (local):** `pg_dump -Fc` → `pg_restore` into a fresh DB in ~1 s: organizations,
  documents, audit entries, findings, 24 RLS-enabled tables, 32 policies and the 3 audit triggers
  identical; audit hash chain re-verified OK on the restored copy. Must be repeated on Neon after deploy.
- **Chaos:** worker crash → expired lease re-claimed (test); provider outage → retry with backoff then
  park (tests + runbook); malformed LLM output → one repair, then baseline + human review (code path).
- **Read latency (in-process TestClient, local Postgres, n=300):** documents list p95 21 ms, analysis
  report p95 26 ms, `/auth/me` p95 17 ms. Not a production load test.
- **Browser e2e (local):** signup → verify → login → upload → processing → verification → policy →
  free scan, with screenshots; injected NC arithmetic error found at the exact amount.
- **Accessibility pass (manual):** labelled inputs, `aria-invalid`/`aria-describedby`, focus-visible
  rings, `role=alert/status`, `aria-current` on the case stepper, table captions/headers. No automated
  axe audit run yet.

## Deployment readiness
- Fly.io configs for api/worker/web (`infra/fly/*.toml`, release-command migrations, `/readyz` checks),
  production config refuses to start with local storage/KMS, non-Claude LLM, missing Stripe/webhook or
  signing secrets, or insecure cookies.
- Runbooks: data deletion, suspected breach, provider outage, wrong finding, local e2e.
- Launch checklist mapped to §11: `docs/LAUNCH_CHECKLIST.md`.

## Not done (needs the founder or accounts)
Actual staging/production deploy, monitoring/alert wiring (Sentry/OTel endpoints), email provider,
Stripe webhook registration, Claude evaluation, attorney review. Nothing was purchased or sent anywhere.

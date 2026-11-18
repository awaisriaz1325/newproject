# Launch checklist (build prompt §11) — status 2026-11-18

| Item | Status | Evidence |
|---|---|---|
| CI checks green: lint, types, unit, integration, cross-tenant, malicious-file, prompt-injection, migrations, dependency + secret scans | ✅ locally (372+ Python tests, web lint/type/test/build); GitHub Actions to confirm on first run | `make check`, `.github/workflows/ci.yml` |
| e2e | ✅ local browser smoke (`tests/e2e/smoke.cjs`); not yet in CI (needs services) | docs/runbooks/local-e2e.md |
| Every production rule has a citation and tests; no candidate rule affects customer numbers | ✅ | `validate_registry()`; `test_candidate_rules_never_reach_customer_numbers` |
| Golden tests: correct audits → zero findings; injected errors found with correct impact | ✅ | packages/rating/tests/test_golden.py |
| SSNs never persist; restricted fields encrypted; access logged and visible | ✅ (FEIN field not yet collected; when added, use envelope encryption) | vault tests, `/access-log` |
| No path sends anything to a carrier | ✅ by design — no carrier integration exists | routes/cases.py |
| Extraction evaluation and cost per scan measured | ⚠️ Baseline measured on synthetic data; **Claude extractor not yet evaluated** (needs FD-06 + API key); cost per scan with LLM is an estimate | docs/ml/extraction.md |
| Backup restore drill | ✅ local pg_dump/pg_restore drill: counts, RLS policies, triggers and audit hash chain identical. ⚠️ Repeat on production Neon (PITR/branch restore) after deploy | phase-9-10 report |
| Threat model updated; every High finding fixed or accepted | ⚠️ See open items in threat model v1.0 (CSP `unsafe-inline`, session rotation on MFA, password reset) | docs/security/threat-model.md |
| Phase 0 legal summary reviewed by attorney | ❌ **Blocking** (FD-01) | docs/FOUNDER_DECISIONS.md |
| Monthly infra cost documented and within budget | ⚠️ Estimated $45–85/mo (cited prices); measure after deploy | docs/phase-0/03-providers-and-costs.md |

## Before first customer
1. FD-01 attorney review → enable states in `jurisdiction_policies` (reviewed data change, audited).
2. FD-06 Anthropic ZDR + key; run `compback_extract.evaluate` with the Claude extractor; record results.
3. FD-07 accounts (Fly, Neon, R2, AWS KMS, Stripe, email provider); set secrets; deploy staging; run
   the browser smoke test against staging; restore drill on Neon.
4. Replace legal placeholders (FD-11). Register Stripe webhook endpoint.

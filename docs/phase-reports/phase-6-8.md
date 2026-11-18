# Phases 6–8 report — ML components, cases & disputes, billing

## Phase 6 — ML
- Class-code review assistant behind `ClassificationReferenceProvider` (licensing gate). Only a
  self-authored placeholder provider ships (`licensed_for_production = False`). TF-IDF retrieval,
  "needs expert review" output only. Measured on 12 self-written examples: top-1 0.833, top-3 1.000
  (harness validation only).
- Finding prioritization baseline (documented priors); extraction quality edit-rate tracker.

## Phase 7 — Free scan → disputes → cases
- Cases with an enforced state machine (draft → ready_for_review → approved_by_customer → submitted →
  carrier_responded → resolved → fee_invoiced → closed; withdraw allowed early). Every transition is a
  case event + audit entry.
- **Paid features gated by jurisdiction policy** (all states off until counsel clears them).
- Dispute package generator: cover letter + itemized schedule from **reviewer-confirmed, active-rule**
  findings only; numbers/citations validated before rendering; PDF (reportlab) + editable DOCX; stored
  envelope-encrypted; versioned; owner approval records fee-terms acceptance.
- **No path sends anything to a carrier**: "submitted" records what the customer did (method, date).
- Deadlines stored only with a stated source; otherwise "Unknown — check your policy or the carrier's
  audit notice". Outcomes require a proof document and reviewer verification.

## Phase 8 — Billing
- `BillingProvider` with Stripe (`StripeClient.v1` customers / invoice items / invoices / finalize,
  idempotency keys per fee — parameters verified against the installed SDK 17.0.0) and a fake for tests.
- Analysis fee (flat) and contingency fee on **verified** recovery only (rate, cap, credit of paid
  analysis fee; transparent calculation lines shown before approval).
- Webhook: signature verification, `stripe_events` idempotency table, invoice paid/void handling,
  dispute events audited for manual handling.

## Checks (real output)
ruff clean · mypy strict clean (68 files) · **372 passed**, coverage 91% · migrate-check OK ·
pip-audit: no known vulnerabilities.

## Bug found and fixed
1-cent drift when the schedule-credit percentage is inferred from printed amounts (snap to the filed
half-percent that reproduces the printed credit).

## Not done / needs founder
- Real Stripe keys and webhook endpoint registration (FD-05/FD-07). Fee amounts are provisional.
- Email delivery provider for deadline reminders (outbox exists; sender not wired) — Phase 10 item.
- Fee refunds/disputes are handled manually via the Stripe dashboard (runbook), not in-app.

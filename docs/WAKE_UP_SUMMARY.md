# What was built overnight (2026-11-18)

Branch: `awais/busy-mendel-x5vxxc` · per-phase reports: `docs/phase-reports/` · decisions to review:
`docs/FOUNDER_DECISIONS.md` · launch gaps: `docs/LAUNCH_CHECKLIST.md`.

## In one paragraph
All 11 phases of the build prompt were implemented end to end: legal/data research with citations,
a multi-tenant FastAPI + Postgres (RLS) backend, a secure document vault (malware scan, local OCR,
SSN redaction in text **and** pixels, envelope encryption), extraction with a Claude adapter and a
deterministic baseline, a cited rules registry + Decimal rating engine with seven detectors, a
licensing-gated class-code assistant, cases/dispute packages (PDF + Word), Stripe invoicing with
idempotent webhooks, and a Next.js web app. 372 Python tests + 7 web tests pass locally; a real
browser run went from signup to a finished free-scan report.

## The three things only you can do
1. **Attorney review (FD-01) — blocks launch.** New York (Ins. Law § 2102(b)(3)) and Virginia (SCC)
   require a license to be paid for reviewing/advising on insurance policies. Paid features are
   therefore **off in every state** until counsel clears states (a data change, no deploy).
2. **Accounts & keys (FD-06/07/13):** Anthropic (request zero data retention), Fly.io, Neon, Cloudflare
   R2, AWS KMS, Stripe, an email provider. Nothing was purchased or signed up for.
3. **Review provisional choices** in `docs/FOUNDER_DECISIONS.md` (fees $499 + 25% capped at $25k,
   in-house auth, no model fallback, findings outside NC limited to document-consistency checks).

## Honest limits
- Rating rules are verified only for **North Carolina** (NCRB Basic Manual). Elsewhere, per-line and
  overtime findings stay internal ("needs expert") by design.
- Extraction accuracy is measured on **synthetic** documents only: perfect on clean PDFs, **69% class-line
  recall on noisy scans** with the no-LLM baseline. The Claude extractor has not been evaluated (needs a key).
- Not deployed; no external pen test; CSP still allows inline scripts; see threat model open items.

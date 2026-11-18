# Phase 0 — Providers, data handling and cost

> Research date: 2026-11-18. Prices are from pages cited below and **must be re-checked at
> purchase time**. Anything without a citation is labeled *estimate*.

## 1. LLM — Anthropic Claude API (default provider behind an adapter)

Data handling (official: [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)):

- "Retained data is never used for model training without your express permission."
- "Conversation content (your prompts and Claude's outputs) is not retained by default; the
  exception is Covered Models, which require 30-day retention." Covered Models = Fable/Mythos 5.x.
- **Zero data retention (ZDR)** is available per organization via Anthropic sales.
- Feature eligibility for ZDR: **PDF support — Yes; Citations — Yes; Prompt caching — Yes;
  Structured outputs — Yes (qualified: only the JSON schema is cached); Batch API — No (29-day
  retention); Files API — No.**

**Decisions:** default model `claude-opus-5-5` (not a Covered Model → ZDR-eligible). Do **not**
use Batch or Files API for customer documents (not ZDR-eligible). Send inline, already-redacted
page images/text only. Request ZDR before production (**FD-06**).

Pricing (per 1M tokens, first-party, from the bundled Claude API reference cached 2026-11-03):
Opus 5.5 $4 in / $20 out; Sonnet 5.5 $2 / $10; Haiku 5.5 $0.10 / $0.50.

## 2. OCR / layout

| Option | Price | Data | Notes |
|---|---|---|---|
| **Tesseract (local, Apache-2.0)** | $0 | never leaves our infra | Required anyway: SSNs on scanned pages must be found **before** any page leaves our infra. |
| AWS Textract DetectDocumentText | $0.0015/page | AWS | [AWS pricing](https://aws.amazon.com/textract/pricing/) (US West Oregon) |
| AWS Textract AnalyzeDocument Forms / Tables | $0.05 / $0.015 per page | AWS | same |
| Claude vision on redacted page images | token-priced | Anthropic (ZDR-eligible) | Structured extraction step |

**Decision (ADR-0005):** local text layer (pypdfium2) + local Tesseract OCR → SSN/TIN redaction
on text **and** page images → Claude structured extraction on redacted inputs. Textract stays an
optional adapter (no AWS dependency at launch).

## 3. Infrastructure (launch scale; budget $50–200/month)

| Item | Choice | Cited price | Monthly estimate |
|---|---|---|---|
| App hosting (web, api, worker) | Fly.io Machines | shared-cpu-1x 256MB $2.19/mo; RAM $6/GB-mo after 2026-10-01 ([Fly pricing update](https://fly.io/pricing-update/)) | 3 × 1GB machines ≈ **$20–25** (estimate) |
| Postgres | Neon (Launch, usage-based) | ~$0.106/CU-hr, ~$0.35/GB-mo (third-party; [Neon FAQ](https://neon.com/faqs/postgres-services-no-minimum-charge) confirms free tier only) | **$20–40** (estimate) |
| Object storage | Cloudflare R2 | $0.015/GB-mo, free egress, 10 GB free ([Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/index.md)) | **<$2** |
| Key management | AWS KMS (1 CMK) | $1/key/mo — `UNVERIFIED` (not fetched) | **~$1** |
| Malware scan | ClamAV in worker image | $0 | $0 |
| Error tracking | Sentry free tier | `UNVERIFIED` | $0 |
| Email | Postmark/Resend | `UNVERIFIED` | $0–15 |
| **Total fixed** | | | **≈ $45–85/month** (estimate, before LLM usage) |

Stripe: Invoicing Starter 0.4% per paid invoice + card processing 2.9% + $0.30
([Stripe support](https://support.stripe.com/questions/stripe-invoicing-pricing)).

## 4. Cost per scan (estimate — to be **measured** in Phase 4)

Assumption: 20-page packet, ~1.6k input tokens per page image + 2k prompt, ~3k output tokens of
JSON, Opus 5.5 → (20×1.6k + 2k) × $4/1M + 3k × $20/1M ≈ **$0.14 + $0.06 ≈ $0.20/scan**.
*Estimate only.* Phase 4 records real `usage` per job into `llm_usage` and the founder dashboard.

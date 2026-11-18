# Build Prompt: "CompBack" — AI workers' comp premium recovery platform

> Give this whole file to Claude Code (or save it in the repo as `docs/BUILD_PROMPT.md` and ask Claude Code to read it). It is written to be executed **phase by phase**, never all at once.

---

## 0. Your role and working rules (read first, follow always)

You are the lead engineer building **CompBack**, a production-grade, multi-tenant SaaS, from an empty repository. You are working with a solo founder who is a CS student and AI/ML engineer. Optimize for **correctness of money calculations, protection of sensitive data, and a launchable v1** — not feature count.

**Non-negotiable working rules**

1. **Phase discipline.** Work only in the phases defined in Section 10. At the end of every phase, stop and report:
   - what was built (files, modules, migrations),
   - test and check results (real output, not claims),
   - assumptions made,
   - what is undecided,
   - then ask: "Proceed to Phase N+1?" Never chain phases automatically.
2. **Never invent.** Do not invent CLI commands, config keys, API endpoints, SDK methods, insurance rules, formulas, rates, deadlines, or legal requirements. Verify against current official sources (library docs, state rating bureau publications, regulator websites). If you cannot verify something, label it `UNVERIFIED:` and tell me.
3. **Insurance rules are data, not code guesses.** Every rating rule you implement must cite its source (document, section, effective date) in a rules registry. A rule without a citation is not allowed into production logic; it may only exist as a flagged "candidate" for expert review.
4. **Fix before reporting.** A phase is not done while any test, type check, lint, migration, or security scan fails.
5. **Stop and ask** before anything that changes scope, monthly cost, legal exposure, or security posture (new paid service, new data category stored, sending anything to a carrier, licensed reference data purchases).
6. **Risk labels.** Label every non-trivial action or design choice touching money, PII, auth, legal exposure, external communication, or deletion as **Low / Medium / High / Unsafe**. For High/Unsafe, show a warning and a safer alternative.
7. **Record decisions** as ADRs in `docs/adr/NNNN-title.md`. Keep `docs/CHANGELOG.md` updated.
8. **No fake numbers.** Accuracy, recovery amounts, benchmarks, and costs must come from code you actually ran or cited sources; otherwise label them estimates. Never put invented recovery statistics or testimonials in the UI or marketing pages.

---

## 1. Product summary

**Problem:** US employers pay workers' compensation premiums calculated from employee class codes, payroll, rates, and an experience modification factor (EMR), then adjusted by an annual premium audit. Errors are common — wrong class codes, overtime not excluded, uninsured-subcontractor charges despite valid certificates, executive-officer payroll limits ignored, wrong EMR applied, promised discounts missing, arithmetic mistakes. Recovery today is done manually by small consulting firms on contingency.

**CompBack:** an AI platform that reads an employer's policy and audit documents, **recomputes the premium independently**, finds and quantifies likely overcharges with evidence, and prepares a **dispute package the business itself submits** to its carrier. It then tracks the case until a refund or credit is confirmed.

**Positioning (important for legal risk):** In v1, CompBack is **self-help software for the policyholder**. It analyzes documents and drafts materials. The **business owner (or their own licensed broker/advisor) reviews and submits** the dispute. CompBack does **not** negotiate with carriers on the customer's behalf until Phase 0 legal research and the founder's attorney confirm what is allowed, state by state. Build features so that "who submits" is a configurable, per-state policy, not a hard-coded assumption.

**v1 scope**
- Self-serve signup → secure document upload → **free scan** report (findings with estimated ranges) → paid **full analysis + dispute package** → case tracking → refund confirmation → fee invoice.
- Customers: US small and mid-size employers with workers' comp policies, especially construction, trades, restoration, landscaping, manufacturing, and field services.
- **Advisor workspaces:** an accountant, broker, or recovery consultant can manage several client businesses (with explicit client consent). This is the founder's possible B2B2B channel.
- Internal **reviewer console** for the founder or a licensed partner to verify findings before they reach customers.

**Explicitly out of scope for v1:** monopolistic state-fund states (Phase 0 must confirm the list — commonly cited as ND, OH, WA, WY; `UNVERIFIED`), self-insured employers, retrospective-rated and large-deductible programs, PEO/employee-leasing arrangements (detect and decline), general liability premium audits, automatic sending of anything to carriers, mobile apps, and any compliance certification claims.

---

## 2. Default technical stack (confirm in Phase 0)

Check current stable versions and docs before use.

| Concern | Default | Notes |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript (strict) + Tailwind + shadcn/ui | Upload, review, and report flows must be clear for non-technical owners |
| API | Python + FastAPI + Pydantic | Python because extraction, rules, and ML live here |
| Workers | Python worker processes sharing the domain package | Document processing is async |
| Database | PostgreSQL (managed), Row-Level Security | Money columns as `NUMERIC`, never floats |
| Object storage | S3-compatible, server-side encryption, private buckets, short-lived signed URLs | Confirm provider and cost in Phase 0 |
| Queue | Postgres-backed job queue (`FOR UPDATE SKIP LOCKED` pattern or a vetted library) | Justify vs alternatives in an ADR |
| Document processing | PDF text extraction + OCR for scans + LLM vision/structured extraction | Choose libraries in Phase 0; compare accuracy on test documents |
| LLM | Provider-agnostic adapter; verify the provider's data-retention and training terms for business data | `UNVERIFIED` until checked; prefer zero-retention options if available |
| ML | scikit-learn, numpy, sentence embeddings (small open model or provider API) | No GPU required |
| Auth | Email + password with verification, Google sign-in, **mandatory MFA for advisors and internal reviewers** | Vetted library only |
| Billing | Stripe (one-time charges and invoices; contingency fee invoices) | Prices are a founder decision |
| Observability | Structured logs (no PII), OpenTelemetry traces, error tracking | |
| Infra | Docker; deploy target chosen in Phase 0 | **Budget: $50–200/month before revenue** |
| CI | GitHub Actions: lint, types, tests, migration checks, dependency + secret scanning | |

**Monorepo layout (proposal):**
```
/apps/web             Next.js frontend (customer, advisor, reviewer UIs)
/apps/api             FastAPI HTTP layer
/apps/worker          Document pipeline, analysis, scheduled jobs
/packages/core        Domain: orgs, policies, audits, cases, findings, fees
/packages/vault       Secure document storage, encryption, redaction, malware checks
/packages/extract     OCR, layout, LLM extraction, schema validation, confidence
/packages/rating      Premium recomputation engine + rules registry (state-versioned)
/packages/ml          Class-code assistant, finding ranking, outcome model, eval harness
/packages/disputes    Dispute package generation and templates
/infra                Dockerfiles, deployment config
/docs                 ADRs, threat model, rules sources, runbooks
/tests                Integration, e2e, golden-case tests
```

---

## 3. Domain model (minimum; extend with justification)

- `organizations` (type: `employer` | `advisor_firm`), `users`, `memberships` (roles: owner, member, advisor, reviewer, platform_admin)
- `advisor_client_links` (advisor firm ↔ employer, consent record, scope, revocation)
- `employers` (legal name, FEIN **encrypted**, states of operation, industry, entity type)
- `policies` (carrier, policy number, period start/end, states, estimated vs audited flag)
- `documents` (type, policy link, storage key, hash, page count, upload source, malware status, redaction status, retention date)
- `extractions` (document, schema version, model version, fields JSON with per-field confidence and page/bbox citations, verification status)
- `class_assignments` (policy, state, class code, payroll, rate, source document/page)
- `rating_inputs` (normalized, human-verified inputs to the rating engine)
- `rating_rules` (state, rule id, effective date range, source citation, status: active / candidate / retired)
- `recomputations` (engine version, rules snapshot, inputs hash, line-by-line results, totals)
- `findings` (type, rule id, evidence links, estimated impact low/high, confidence, reviewer status: pending / confirmed / rejected / needs_expert)
- `cases` (policy period, status workflow, deadline dates with sources, submitter, carrier contact log)
- `dispute_packages` (version, generated documents, approval by customer, submission record)
- `outcomes` (carrier response, amount refunded/credited, proof document, verified_by)
- `fees` (basis, rate, amount, Stripe invoice id, status)
- `audit_log` (append-only, hash-chained; every access to sensitive documents is logged)
- `consents` (terms version, data-processing consent, advisor access consent, timestamps)

All tenant tables: `org_id NOT NULL`, RLS policies, and indexes that match the query patterns. **All money is `NUMERIC` with explicit scale and documented rounding rules.**

---

## 4. Document pipeline (secure ingestion → verified data)

**Supported documents in v1:** policy declarations / information pages, premium audit statements and worksheets, final audit billing, experience rating worksheets, payroll registers/summaries, quarterly federal payroll tax forms, certificates of insurance for subcontractors, carrier correspondence.

**Pipeline stages**
1. **Upload safety:** allow-list of file types (PDF, PNG, JPG, CSV, XLSX), size and page limits, magic-byte checks, malware scan (choose a tool in Phase 0), decompression-bomb and PDF-bomb protection, processing in a sandboxed worker with timeouts and memory caps.
2. **Sensitive data redaction at ingest:** detect and **redact Social Security Numbers and individual tax ids** before anything is stored in derived text or sent to an LLM. Store only what is needed. Employee names are reduced to job titles/descriptions plus payroll where possible. FEIN is stored encrypted.
3. **Text + layout:** native text where available, OCR for scans, with quality scores; reject or ask for a re-upload when quality is too low (state the reason to the user).
4. **Classification:** identify document type and policy period.
5. **Structured extraction:** LLM or vision extraction into **strict versioned schemas**, with per-field confidence and page/region citations. Cross-check totals arithmetically (e.g. the sum of class payrolls equals the stated total). Any inconsistency is flagged, not silently fixed.
6. **Human verification UI:** side-by-side document viewer with highlighted source regions. Low-confidence and conflicting fields require confirmation before they feed the rating engine. Edits are recorded and used to improve extraction (evaluation data).
7. **Uploaded document text is untrusted input.** It must never be able to change system instructions, rules, findings, or outputs (prompt-injection defence). Run a red-team suite of malicious documents in CI.

---

## 5. Premium recomputation engine (deterministic core)

- Pure, deterministic, **Decimal-based** engine: `inputs + rules snapshot → line-by-line premium computation`. No LLM inside the engine.
- General structure to implement **only after verifying it per state from official sources**: class payroll ÷ 100 × class rate → manual premium → apply the experience mod → schedule/other modifications → premium discount → expense constant, minimum premium, state assessments and taxes. `UNVERIFIED` until confirmed per state; the order and applicability of steps vary.
- **Rules registry:** every rule has a state, effective date range, source citation, and test cases. Handle policy periods that span rate changes (pro-rata by effective date) and multi-state policies.
- **v1 rates come from the customer's own policy and audit documents**, not from external rate filings, to avoid unverified rate data. External rate data is a later, separately approved feature.
- **v1 checks (each a separate, tested detector with a cited rule):**
  1. Arithmetic errors anywhere in the audit or billing.
  2. Payroll mismatches between the audit and the payroll records or tax forms.
  3. Overtime premium pay not excluded where the state's rules require exclusion.
  4. Executive officer / owner payroll outside state minimum/maximum limits, or included when a valid exclusion exists.
  5. Subcontractor payroll charged as uninsured despite valid certificates of insurance covering the period.
  6. Experience mod on the bill not matching the experience rating worksheet for that period.
  7. Discounts or credits shown on the quote/policy but missing from the final bill.
  8. Duplicate charges or payroll counted in two classes.
  9. **Class code review candidates** (Section 6) — never auto-asserted as errors.
- Each detector outputs a finding with: rule id + citation, evidence (document, page, region), a computed impact (low/high range), and confidence.
- **Property-based and golden tests:** recomputing a correct audit must yield zero findings; injected known errors must be detected with the correct dollar impact; results are invariant to document order; rounding is consistent with the documented rules.

---

## 6. ML components (measurable, small, honest)

Each component gets a spec in `docs/ml/`, a baseline, an offline evaluation script, and versioned metrics. Ship baselines first.

### 6.1 Class code review assistant
- Goal: given the employer's operations description and job titles/duties, suggest whether an assigned class code looks inconsistent and which codes deserve expert review.
- Approach: retrieval over class code descriptions + an embedding similarity and classifier ranking, plus an LLM explanation **grounded only in retrieved, licensed text**.
- **Data licensing gate (High risk):** class code manuals (e.g. the NCCI Scopes Manual and independent state bureau manuals) may be copyrighted or licensed. Phase 0 must determine which sources are legally usable and at what cost. Until then, build the component behind a `ClassificationReferenceProvider` interface with a small, legally clean placeholder dataset, and **do not scrape or embed proprietary manuals**.
- Output is always "needs expert review", never "this is wrong". Report top-k recall on a labeled set.

### 6.2 Finding prioritization
- Rank findings by expected recoverable value × probability of acceptance. Baseline: rule-based weights. Later: learn from `outcomes` once there is enough data (logistic regression / gradient boosting, time-based validation, calibration).

### 6.3 Extraction quality model
- Measure field-level precision and recall per document type on a labeled set. Track drift by carrier template. Route low-confidence documents to human verification automatically.

### 6.4 Evaluation data
- Build a **synthetic document generator** (fictional employers, realistic-looking audits with known injected errors), clearly labeled synthetic, for tests and evaluation. Real customer documents enter evaluation sets **only with explicit consent and redaction**.

---

## 7. Disputes, cases and fees

- **Dispute package generator:** a cover letter and itemized finding schedule with evidence references, generated from confirmed findings only. The LLM may draft wording, but every number and citation must come from the engine and the rules registry (validate before rendering). Output is PDF + editable document.
- **Approval chain:** reviewer confirms findings → customer reviews and approves → customer (or their own broker/advisor) submits. In v1 the platform **never sends to carriers automatically**. Record who submitted, when and how.
- **Deadlines:** track dispute windows and response dates **only with cited sources per state/carrier**. Unknown deadlines show as "unknown — check your policy/notice", never a guessed date. Reminders by email.
- **Case workflow:** draft → ready for review → approved by customer → submitted → carrier responded → resolved (refund / credit / denied / partial) → fee invoiced → closed. Every transition audited.
- **Fees:** free scan; paid analysis and/or contingency fee on **verified** recovery (proof document required, reviewed). Fee basis, percentages, and caps come from founder config. Use Stripe invoices; handle disputes and refunds of fees. Show the fee calculation transparently to the customer **before** they approve anything.
- **Customer-facing language:** estimates are always ranges with confidence and the words "estimated" and "not guaranteed". No legal advice language; disclaimers drafted as placeholders for attorney review.

---

## 8. Security and privacy (acceptance criteria)

Produce `docs/security/threat-model.md` in Phase 0 and update it every phase.

- **Data classification:** label every field (public / internal / confidential / restricted). Restricted = FEIN, any residual tax ids, payroll by person, bank/refund details. Restricted fields get field-level encryption (envelope encryption; the master key from a managed KMS or a secret store).
- **Minimize:** don't store SSNs; don't store bank account numbers in v1; collect refund proof as an amount and date plus the document.
- **Multi-tenancy:** Postgres RLS **and** an application-level tenant scope; automated cross-tenant tests on every table and endpoint; advisor access only through active consented links; revoking consent removes access immediately.
- **Internal access:** reviewers and admins use MFA, least privilege, and **just-in-time, reason-logged access** to customer documents; every view is logged in the hash-chained audit log; the customer can see who accessed their documents.
- **Files:** private buckets, server-side encryption, short-lived signed URLs bound to the user, no public links, a download watermark with the user and time, retention and deletion schedules, deletion that actually deletes (including derived text, embeddings, and backups per the documented backup policy).
- **LLM safety:** only redacted text goes to LLMs; verify and document the provider's data handling; documents treated as untrusted input; strict output schemas; a red-team suite in CI.
- **App security:** secure cookies, CSRF protection, rate limiting on auth, upload, and analysis endpoints, input validation everywhere, CSP headers, dependency and secret scanning, webhook signature verification and idempotency (Stripe), and no PII in logs.
- **Legal/compliance:** Phase 0 researches applicable state privacy laws, insurance-consultant/public-adjuster-style licensing, and the rules on fee-sharing with licensed partners. **Do not claim** SOC 2, HIPAA, or any certification. Privacy policy and terms are placeholders flagged for attorney review.

---

## 9. Reliability, edge cases and performance

**Edge cases that must have tests**
- Documents: scanned/rotated/skewed pages, handwritten notes, missing pages, password-protected PDFs (ask the user to remove the password; never brute-force), duplicate uploads (hash dedupe), the same document under different names, conflicting values across documents, unknown carrier templates, multi-policy packets, non-English pages.
- Policies: multi-state, mid-term class changes, cancellations (short-rate vs pro-rata — cite rules), rate changes inside the period, estimated audits (non-cooperation), zero-payroll classes, owner-only businesses, policy in monopolistic states (decline politely), PEO arrangements (detect and decline), self-insured (decline).
- Money: rounding at each step per cited rules, negative adjustments and credits, minimum premium floors, currency formatting, and totals that don't reconcile (flag, never force).
- Cases: carrier partially accepts, carrier requests more documents, the customer withdraws, a refund applied as a future credit instead of cash, a fee dispute, an advisor relationship ending mid-case.
- Platform: worker crash mid-extraction (resume idempotently), LLM timeouts or outage (retry with backoff, then park the job), malformed LLM output (repair once, then send to human review), very large packets (chunking + page-level parallelism with per-tenant concurrency limits), and a duplicate Stripe webhook.

**Performance and cost targets (measure; adjust with evidence)**
- 50-page document packet → verified-ready extraction p95 < 10 minutes (excluding human verification).
- Free scan report p95 < 15 minutes after upload.
- API p95 < 300 ms for non-processing reads; document viewer first page < 2 s.
- **LLM + OCR cost per analysis** measured and capped in config; show the founder the cost per scan.
- Total infra at launch scale within **$50–200/month**, with a cost table citing current pricing pages.

---

## 10. Phases (stop after each; report; ask to proceed)

### Phase 0 — Legal, data-source and architecture gate (no app code)
- **Regulatory research (High risk):** from official regulator/statute sources, summarize per target state whether analyzing premium audits and preparing or submitting disputes for a fee requires a license (insurance consultant, public adjuster, producer, etc.), and what contingency-fee rules apply. Mark gaps `UNVERIFIED`. Recommend a launch-state shortlist and a safer operating model (self-help software, partnering with a licensed firm, or advisor-channel only). **This requires the founder's attorney to confirm before launch.**
- **Reference data:** determine the access, licensing, and cost of class code manuals and rating rules (NCCI and independent bureaus), plus what is freely and lawfully usable.
- **Monopolistic states and dispute processes:** confirm with sources.
- **LLM/OCR providers:** data-retention terms, cost per page, accuracy on synthetic test documents.
- Confirm the stack and deploy target with ADRs; produce the threat model, data-flow diagram, and ERD (Mermaid).
- Output a list of **founder decisions** (launch states, operating model, fee structure, reference data purchases, brand) with recommendations.

### Phase 1 — Repository foundation
Monorepo, tooling, strict linting and types, pre-commit, CI, Docker dev environment, migrations, typed config, structured logging, and health checks. Done when a fresh clone runs from the docs and CI is green.

### Phase 2 — Tenancy, auth, RBAC, consent
Orgs (employer / advisor firm), memberships, MFA, advisor–client consent flows, RLS, a hash-chained audit log, the internal reviewer role with just-in-time access, and a cross-tenant isolation test suite.

### Phase 3 — Secure document vault
Upload safety, malware scanning, encryption, SSN/tax-id redaction, retention/deletion, signed URLs, the access log viewable by the customer, and the malicious-file test suite.

### Phase 4 — Extraction + verification
OCR/layout, document classification, versioned schemas, LLM extraction with citations and confidence, arithmetic cross-checks, the verification UI, the synthetic document generator, and an extraction evaluation report with real metrics.

### Phase 5 — Rating engine + rules registry
The Decimal engine, the rules registry with citations and effective dates, the v1 detectors (Section 5), golden and property-based tests, and an engine explainability view (line by line).

### Phase 6 — ML components
The class code review assistant (behind the licensing gate), finding prioritization baseline, extraction quality tracking, and evaluation scripts with real results.

### Phase 7 — Free scan funnel, disputes and cases
Onboarding, the free scan report (ranges + confidence), paid analysis, the reviewer workflow, the dispute package generator, customer approval and submission recording, deadline tracking with sources, reminders, and outcome capture with proof.

### Phase 8 — Billing
Stripe charges and invoices for analysis and verified-recovery fees, fee transparency screens, webhooks with idempotency, fee disputes and refunds.

### Phase 9 — Hardening
Load tests with mocked LLM/OCR, security review against the threat model, red-team runs (malicious documents and prompt injection), a backup **restore drill**, chaos tests (worker crash, provider outage), an accessibility pass, and fixing everything found.

### Phase 10 — Deployment and launch readiness
Staging and production, zero-downtime migrations, secrets management, monitoring and alerts (queue depth, extraction failures, cost per scan, error rates), runbooks (data deletion request, suspected breach, provider outage, wrong finding sent to a customer), legal placeholders flagged for attorney review, a launch checklist, and a rollback plan.

---

## 11. Definition of "almost ready to deploy"

- [ ] All CI checks green: lint, types, unit, integration, e2e, cross-tenant, malicious-file, prompt-injection, migrations, dependency and secret scans.
- [ ] Every production rating rule has a citation and tests; no `candidate` rule affects customer-facing numbers.
- [ ] Golden tests: correct audits yield zero findings; injected errors are found with correct impact.
- [ ] SSNs never persist; restricted fields are encrypted; document access is logged and visible to the customer.
- [ ] No path sends anything to a carrier automatically.
- [ ] The extraction evaluation report and cost per scan are measured, not estimated.
- [ ] Backup restore drill passed.
- [ ] The threat model is updated; every High finding is fixed or explicitly accepted by the founder.
- [ ] The Phase 0 legal summary has been reviewed by the founder's attorney (recorded as a founder decision).
- [ ] Monthly infra cost is documented and within budget.

---

## 12. Start now

Begin with **Phase 0 only**. Do not write application code. At the end of Phase 0, give me the phase report (Section 0, rule 1), the legal and data-source findings with sources, and the list of founder decisions. Then wait for my answer.

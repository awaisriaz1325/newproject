# Phase 3 report — Secure document vault

**Built**
- `compback_vault.filesafety`: allow-list (PDF, PNG, JPG, CSV, XLSX) by magic bytes + extension match,
  size limits, truncated-PDF check, XLSX structure / macro / path-traversal / decompression-bomb checks.
- `compback_vault.malware`: ClamAV `clamd` INSTREAM client (protocol tested against a fake server);
  scanner errors are retried, never treated as clean. Dev/test uses an EICAR-only scanner; staging/prod
  **require** `COMPBACK_CLAMAV_HOST`.
- `compback_vault.redaction`: SSN/ITIN/contextual-TIN detection with a documented policy (EIN kept and
  encrypted; masked values left alone); returns spans/counts, never values.
- `compback_vault.pages`: native text (pypdfium2) **and** local Tesseract OCR on every rendered page;
  identifiers removed from text and **blacked out in pixels** (char boxes for native text, word boxes for
  OCR). Low OCR confidence flagged. Password-protected PDFs rejected with "remove the password" (never
  brute-forced). CSV/XLSX tables redacted by header and content.
- `compback_vault.sandbox`: processing runs in a spawned child with RLIMIT_AS / RLIMIT_CPU / no core
  dumps and a wall-clock timeout.
- `compback_vault.service`: encrypt-then-store originals (envelope, context-bound), hash dedupe per org,
  ingest job (scan → sandboxed processing → encrypted redacted pages), hard delete of original + page
  images + derived text, retention sweep.
- `compback_core.queue`: SKIP LOCKED claims, leases (crash recovery), exponential backoff, parking,
  idempotency keys, per-org concurrency limit. Worker runner + hourly retention sweep.
- API: upload, list, detail, redacted page image (watermarked: viewer email + UTC time) and text, short-lived
  HMAC download links bound to user + document (session also required), watermarked redacted PDF
  download, owner-only delete. Every view/download is audited and visible in the customer access log.
- Migrations 0004 (documents, pages + RLS) and 0005 (worker may append audit entries).

**Check results (real output)**
- ruff: all checks passed · mypy strict: 42 files, no issues · pytest: **147 passed**, coverage 91% ·
  migrate-check: round-trip OK, no drift.
- Malicious-file suite: renamed executables, ELF, HTML, truncated PDF, zip bomb, macro workbook, archive
  path traversal, plain zip, decompression-bomb PNG (64M px in <200 KB), corrupt PDF, EICAR, password PDF.
- Redaction: property test (formatted SSNs never survive in any surrounding text); re-OCR of a redacted
  image finds no SSN digits (pixels removed, not just text).

**Bugs found by tests and fixed:** exception not picklable across the sandbox boundary; ambiguous SQL
parameter type in queue failure update; worker could not audit retention deletions (new migration 0005).

**Not verified here:** a real `clamd` with signature DB (freshclam needs network access to the ClamAV
mirror); covered by the protocol test and compose service.

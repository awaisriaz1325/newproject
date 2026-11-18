# ADR-0005: Local OCR and redaction before any external processing

- Status: accepted · Date: 2026-11-18 · Risk: **High** (PII)

## Context
Payroll registers and tax forms contain SSNs. Build rule: SSNs/TINs are redacted before anything is
stored as derived text or sent to an LLM. A scanned page's SSN is only discoverable by OCR — so OCR
must run inside our infrastructure.

## Decision
1. Upload safety (allow-list, magic bytes, size/page caps, ClamAV, PDF bomb limits) in a sandboxed worker.
2. Text layer via `pypdfium2`; scanned pages via local **Tesseract** with word boxes.
3. Detect SSN / ITIN / individual TIN patterns (with context and validity rules) → replace in text and
   **black-box the pixels** in page images. The original file stays encrypted in the vault (needed as
   evidence); only redacted derivatives are used downstream.
4. LLM structured extraction gets redacted page images + redacted text only.

## Consequences
Worker image includes tesseract + clamav. Redaction recall is tested with a synthetic SSN corpus.

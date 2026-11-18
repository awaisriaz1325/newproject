# Runbook: LLM / OCR / storage / Stripe outage

- **LLM (Anthropic) outage:** extraction jobs raise `LLMUnavailableError` → retried with exponential
  backoff (10 s … 1 h) and **parked** after 5 attempts. Optionally switch `COMPBACK_LLM_PROVIDER` to
  `heuristic` temporarily (all extractions then go to human review). After recovery, re-queue parked jobs:
  `UPDATE jobs SET state='queued', attempts=0, run_after=now() WHERE state='parked' AND kind='document.extract'`.
- **Malware scanner down:** ingest jobs retry (never treated as clean); uploads keep queueing.
- **Object storage down:** uploads fail fast with 5xx; nothing is half-written to the DB (storage write
  happens before the row is committed).
- **Stripe down:** invoice creation fails → the request errors and no fee row is committed; retry is
  safe (idempotency keys). Webhooks are retried by Stripe and deduplicated by `stripe_events`.

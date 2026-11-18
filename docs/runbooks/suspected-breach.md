# Runbook: suspected breach or unauthorized access

1. **Contain (minutes):** rotate `COMPBACK_SIGNING_SECRET`, Stripe keys and Anthropic key; revoke all
   sessions (`UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL` as owner); disable the
   suspected account (`users.disabled_at`). If storage credentials may be exposed, rotate them; data
   stays protected by envelope encryption unless the KMS key is also exposed — then disable the KMS key
   grant for the old role and rewrap.
2. **Preserve evidence:** snapshot the database (Neon branch), export `audit_log` and application logs.
   Do not modify `audit_log` (append-only; triggers block edits).
3. **Scope:** use `audit_log` (`document.viewed`, `document.downloaded`, `access_grant.created`) and the
   hash-chain verifier (`GET /orgs/{id}/audit/verify`) per affected organization.
4. **Notify:** founder + attorney decide on notifications under applicable state breach-notification
   laws (`UNVERIFIED` per state — counsel). SSNs are never stored, which narrows exposure.
5. **Post-incident:** root cause, threat-model update, regression test.

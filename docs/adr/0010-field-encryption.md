# ADR-0010: Envelope encryption for restricted fields and documents

- Status: accepted · Date: 2026-11-18 · Risk: **High** (security)

## Decision
AES-256-GCM via `cryptography` (AESGCM). Each record/document gets a random 256-bit data key; the data
key is wrapped by a master key from a `KeyProvider` (`LocalKeyProvider` for dev/test from env;
`AwsKmsKeyProvider` for prod). Ciphertext format is versioned (`v1:` + key id + nonce + ct) and bound to
context via AAD (`table:column:row_id:org_id`) so ciphertext can't be swapped between rows/tenants.
Restricted fields (FEIN, residual tax ids, per-person payroll) use this; object storage additionally uses
provider SSE.

## Consequences
Key rotation = rewrap data keys. Losing the master key loses data → KMS with deletion protection.

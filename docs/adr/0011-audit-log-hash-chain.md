# ADR-0011: Append-only, hash-chained audit log

- Status: accepted · Date: 2026-11-18 · Risk: Medium

## Decision
`audit_log` rows are insert-only (DB role has no UPDATE/DELETE grant; trigger rejects updates/deletes).
Each row stores `prev_hash` and `hash = SHA-256(prev_hash || canonical_json(row))`, chained per org.
A verifier walks the chain. Every sensitive document view writes an entry the customer can see.

## Consequences
Concurrent writers serialize per org with an advisory lock (low volume, acceptable).

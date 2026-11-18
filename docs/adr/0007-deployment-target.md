# ADR-0007: Deployment target

- Status: proposed (needs founder sign-off on accounts) · Date: 2026-11-18 · Risk: Medium (cost)

## Decision
Fly.io (web, api, worker Machines) + Neon Postgres + Cloudflare R2 (S3 API) + AWS KMS for the master key.
Estimated $45–85/month before LLM usage (see `docs/phase-0/03-providers-and-costs.md`).

## Alternatives
AWS-only (ECS/RDS/S3/KMS): more "enterprise", ~2–3× cost at launch scale, more ops. Render/Railway:
comparable. Vercel for web: Pro plan needed for commercial use.

## Consequences
Everything is Docker + S3-compatible + plain Postgres, so migration to AWS later is straightforward.

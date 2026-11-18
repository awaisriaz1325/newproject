# ADR-0004: Authentication and sessions

- Status: accepted · Date: 2026-11-18 · Risk: **High** (auth)

## Decision
Backend-owned auth in FastAPI using vetted primitives:
- Passwords: **argon2id** via `argon2-cffi` (OWASP-recommended algorithm).
- MFA: **TOTP (RFC 6238)** via `pyotp`; **mandatory** for `advisor`, `reviewer`, `platform_admin` roles;
  recovery codes stored hashed.
- Sessions: opaque random tokens (256-bit, `secrets`), only a SHA-256 hash stored server-side; cookie
  `__Host-` prefixed, `Secure`, `HttpOnly`, `SameSite=Lax`; idle + absolute expiry; rotation on login
  and privilege change.
- CSRF: double-submit token header for state-changing requests.
- Google sign-in: OIDC (planned in Phase 2b via `authlib`), linked to verified email only.
- Rate limiting on auth endpoints.

## Alternatives
Hosted auth (Clerk, WorkOS, Auth0): faster and market-standard, but adds a paid processor of user PII,
vendor lock-in and MFA-policy limits at the free tier. **Safer alternative if the founder prefers:**
WorkOS AuthKit (decision FD-08). The session/identity layer is behind an interface so this can switch.

## Consequences
We own security-critical code → covered by unit tests, rate limits, and Phase 9 review.

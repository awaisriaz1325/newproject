# ADR-0013: Row-level security design

- Status: accepted · Date: 2026-11-18 · Risk: **High** (multi-tenancy)

## Decision
- The API/worker connect as `compback_app` (not table owner, NOBYPASSRLS) → RLS always applies.
  Tables are **not** `FORCE`d: the owner role is used only by migrations and by narrowly scoped
  `SECURITY DEFINER` helper functions (`compback.org_access_ok()`, `my_org_ids()`,
  `find_org_by_invite_code()`, `audit_chain()`), all with `SET search_path = public, pg_temp`.
- Each transaction sets `app.org_id`, `app.user_id`, `app.actor_kind` (transaction-local).
- Tenant policies: `org_id = current_org_id() AND (SELECT org_access_ok())`. The sub-select makes the
  access check an init-plan evaluated once per statement. `org_access_ok()` re-derives access from
  memberships, **active** advisor links, or unexpired reviewer grants — so revoking consent removes
  access in the database too, not only in the app.
- Actor kinds `auth` (signup/login lookups), `system` (internal checks) and `worker` widen access and
  are only set by server code paths; they are never derived from request input.
- `audit_log`: INSERT-only for the app role; UPDATE/DELETE/TRUNCATE revoked and blocked by triggers;
  hash chain computed by a trigger, so application code cannot forge `prev_hash`/`hash`.
  Inserts skip `RETURNING` because writers may append entries they cannot read.
- The application *also* authorizes every org-scoped request explicitly (`resolve_access`) and returns
  404 for inaccessible orgs.

## Consequences
A test asserts every public table has RLS enabled unless it is on a short documented global list,
and every org-scoped GET endpoint returns 404 to another tenant.

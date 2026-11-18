"""tenancy auth consent audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18 11:39:56.704946
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_UP = r'''
-- ---------- access helpers (SECURITY DEFINER: run as owner, which is not subject to RLS) ----
CREATE OR REPLACE FUNCTION compback.org_access_ok() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT compback.current_org_id() IS NOT NULL AND (
    compback.current_actor_kind() IN ('worker', 'system')
    OR EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.org_id = compback.current_org_id() AND m.user_id = compback.current_user_id())
    OR EXISTS (
      SELECT 1 FROM advisor_client_links l
      JOIN memberships m ON m.org_id = l.advisor_org_id
       AND m.user_id = compback.current_user_id() AND m.role IN ('owner', 'advisor')
      WHERE l.client_org_id = compback.current_org_id() AND l.status = 'active')
    OR EXISTS (
      SELECT 1 FROM access_grants g
      WHERE g.org_id = compback.current_org_id()
        AND g.grantee_user_id = compback.current_user_id()
        AND g.revoked_at IS NULL AND g.expires_at > now())
  )
$$;

CREATE OR REPLACE FUNCTION compback.my_org_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT org_id FROM memberships WHERE user_id = compback.current_user_id()
$$;

CREATE OR REPLACE FUNCTION compback.is_auth_actor() RETURNS boolean
LANGUAGE sql STABLE AS $$ SELECT compback.current_actor_kind() IN ('auth', 'system') $$;

CREATE OR REPLACE FUNCTION compback.is_platform_staff() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM users WHERE id = compback.current_user_id()
                 AND is_platform_staff AND disabled_at IS NULL)
$$;

-- Lets an advisor firm find an employer by the invite code the employer shared.
CREATE OR REPLACE FUNCTION compback.find_org_by_invite_code(p_code text)
RETURNS TABLE (id uuid, name text, kind text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT o.id, o.name::text, o.kind::text FROM organizations o
  WHERE o.invite_code = p_code AND o.kind = 'employer'
$$;

-- ---------- RLS ----------
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_select ON organizations FOR SELECT USING (
  id IN (SELECT compback.my_org_ids())
  OR (id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
  OR compback.is_auth_actor());
CREATE POLICY org_insert ON organizations FOR INSERT WITH CHECK (compback.is_auth_actor());
CREATE POLICY org_update ON organizations FOR UPDATE
  USING (id = compback.current_org_id() AND (SELECT compback.org_access_ok()));

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_rw ON users FOR ALL
  USING (id = compback.current_user_id() OR compback.is_auth_actor())
  WITH CHECK (id = compback.current_user_id() OR compback.is_auth_actor());

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY sessions_rw ON sessions FOR ALL
  USING (user_id = compback.current_user_id() OR compback.is_auth_actor())
  WITH CHECK (user_id = compback.current_user_id() OR compback.is_auth_actor());

ALTER TABLE email_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY email_tokens_rw ON email_tokens FOR ALL
  USING (user_id = compback.current_user_id() OR compback.is_auth_actor())
  WITH CHECK (user_id = compback.current_user_id() OR compback.is_auth_actor());

ALTER TABLE email_outbox ENABLE ROW LEVEL SECURITY;
CREATE POLICY outbox_rw ON email_outbox FOR ALL
  USING (to_user_id = compback.current_user_id() OR compback.is_auth_actor()
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK (to_user_id = compback.current_user_id() OR compback.is_auth_actor());

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY memberships_select ON memberships FOR SELECT USING (
  user_id = compback.current_user_id()
  OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
  OR compback.is_auth_actor());
CREATE POLICY memberships_insert ON memberships FOR INSERT WITH CHECK (
  compback.is_auth_actor()
  OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok())));
CREATE POLICY memberships_modify ON memberships FOR UPDATE
  USING (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()));
CREATE POLICY memberships_delete ON memberships FOR DELETE
  USING (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()));

ALTER TABLE advisor_client_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY links_rw ON advisor_client_links FOR ALL
  USING ((advisor_org_id = compback.current_org_id() OR client_org_id = compback.current_org_id())
         AND (SELECT compback.org_access_ok()))
  WITH CHECK ((advisor_org_id = compback.current_org_id()
               OR client_org_id = compback.current_org_id())
              AND (SELECT compback.org_access_ok()));

ALTER TABLE access_grants ENABLE ROW LEVEL SECURITY;
CREATE POLICY grants_select ON access_grants FOR SELECT USING (
  grantee_user_id = compback.current_user_id()
  OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok())));
CREATE POLICY grants_insert ON access_grants FOR INSERT WITH CHECK (
  grantee_user_id = compback.current_user_id() AND compback.is_platform_staff());
CREATE POLICY grants_update ON access_grants FOR UPDATE USING (
  grantee_user_id = compback.current_user_id()
  OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok())));

ALTER TABLE consents ENABLE ROW LEVEL SECURITY;
CREATE POLICY consents_rw ON consents FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.is_auth_actor())
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.is_auth_actor());

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY jobs_rw ON jobs FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');

-- Global reference data: read-only for the app role.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON jurisdiction_policies FROM compback_app;

-- ---------- audit log: append-only + hash chain ----------
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_select ON audit_log FOR SELECT
  USING (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()));
CREATE POLICY audit_insert ON audit_log FOR INSERT WITH CHECK (
  org_id IS NULL
  OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
  OR compback.is_auth_actor());
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM compback_app;

CREATE OR REPLACE FUNCTION compback.audit_payload(a audit_log) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_build_object(
    'org_id', a.org_id, 'seq', a.seq, 'actor_user_id', a.actor_user_id,
    'actor_kind', a.actor_kind, 'action', a.action, 'target_type', a.target_type,
    'target_id', a.target_id, 'reason', a.reason, 'details', a.details,
    'created_at', to_char(a.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
  )::text
$$;

CREATE OR REPLACE FUNCTION compback.audit_chain() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  last_hash text;
  last_seq bigint;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(COALESCE(NEW.org_id::text, 'global'), 42));
  IF NEW.org_id IS NULL THEN
    SELECT hash, seq INTO last_hash, last_seq FROM audit_log
      WHERE org_id IS NULL ORDER BY seq DESC LIMIT 1;
  ELSE
    SELECT hash, seq INTO last_hash, last_seq FROM audit_log
      WHERE org_id = NEW.org_id ORDER BY seq DESC LIMIT 1;
  END IF;
  NEW.created_at := clock_timestamp();
  NEW.seq := COALESCE(last_seq, 0) + 1;
  NEW.prev_hash := COALESCE(last_hash, repeat('0', 64));
  NEW.hash := encode(sha256(convert_to(NEW.prev_hash || compback.audit_payload(NEW), 'UTF8')),
                     'hex');
  RETURN NEW;
END $$;

CREATE TRIGGER audit_chain BEFORE INSERT ON audit_log
  FOR EACH ROW EXECUTE FUNCTION compback.audit_chain();

CREATE OR REPLACE FUNCTION compback.audit_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END $$;

CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION compback.audit_immutable();
CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION compback.audit_immutable();

GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA compback TO compback_app;
'''

RLS_DOWN = r'''
DROP TRIGGER IF EXISTS audit_no_truncate ON audit_log;
DROP TRIGGER IF EXISTS audit_no_update ON audit_log;
DROP TRIGGER IF EXISTS audit_chain ON audit_log;
DROP FUNCTION IF EXISTS compback.audit_immutable() CASCADE;
DROP FUNCTION IF EXISTS compback.audit_chain() CASCADE;
DROP FUNCTION IF EXISTS compback.audit_payload(audit_log) CASCADE;
DROP FUNCTION IF EXISTS compback.find_org_by_invite_code(text) CASCADE;
DROP FUNCTION IF EXISTS compback.is_platform_staff() CASCADE;
DROP FUNCTION IF EXISTS compback.is_auth_actor() CASCADE;
DROP FUNCTION IF EXISTS compback.my_org_ids() CASCADE;
DROP FUNCTION IF EXISTS compback.org_access_ok() CASCADE;
'''


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=True),
    sa.Column('seq', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('actor_kind', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=True),
    sa.Column('target_id', sa.String(length=100), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), server_default='', nullable=False),
    sa.Column('hash', sa.String(length=64), server_default='', nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index('ix_audit_org_seq', 'audit_log', ['org_id', 'seq'], unique=False)
    op.create_index('ix_audit_target', 'audit_log', ['org_id', 'target_type', 'target_id'], unique=False)
    op.create_table('jurisdiction_policies',
    sa.Column('code', sa.String(length=2), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('monopolistic', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('free_scan_allowed', sa.Boolean(), nullable=False),
    sa.Column('paid_analysis_allowed', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('contingency_allowed', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('submitter_mode', sa.String(length=30), server_default='customer_only', nullable=False),
    sa.Column('notes', sa.Text(), server_default='', nullable=False),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('reviewed_by_counsel_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("submitter_mode IN ('customer_only','customer_or_own_advisor','licensed_partner')", name=op.f('ck_jurisdiction_policies_submitter_mode')),
    sa.CheckConstraint('NOT (monopolistic AND (free_scan_allowed OR paid_analysis_allowed))', name=op.f('ck_jurisdiction_policies_monopolistic_declined')),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_jurisdiction_policies'))
    )
    op.create_table('organizations',
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('invite_code', sa.String(length=16), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('employer', 'advisor_firm', 'platform')", name=op.f('ck_organizations_kind')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    sa.UniqueConstraint('invite_code', name=op.f('uq_organizations_invite_code'))
    )
    op.create_table('rate_limit_counters',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('count', sa.Integer(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('key', 'window_start', name=op.f('pk_rate_limit_counters'))
    )
    op.create_table('users',
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_hash', sa.Text(), nullable=True),
    sa.Column('totp_secret_enc', sa.LargeBinary(), nullable=True),
    sa.Column('mfa_enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('recovery_code_hashes', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('is_platform_staff', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('failed_logins', sa.Integer(), server_default='0', nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('access_grants',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('grantee_user_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('char_length(reason) >= 10', name=op.f('ck_access_grants_reason_len')),
    sa.CheckConstraint('expires_at > created_at', name=op.f('ck_access_grants_expiry')),
    sa.ForeignKeyConstraint(['grantee_user_id'], ['users.id'], name=op.f('fk_access_grants_grantee_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_access_grants_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_access_grants'))
    )
    op.create_index('ix_grants_org_user', 'access_grants', ['org_id', 'grantee_user_id'], unique=False)
    op.create_table('advisor_client_links',
    sa.Column('advisor_org_id', sa.UUID(), nullable=False),
    sa.Column('client_org_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('scope', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('requested_by', sa.UUID(), nullable=False),
    sa.Column('approved_by', sa.UUID(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by', sa.UUID(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'active', 'revoked')", name=op.f('ck_advisor_client_links_status')),
    sa.CheckConstraint('advisor_org_id <> client_org_id', name=op.f('ck_advisor_client_links_distinct_orgs')),
    sa.ForeignKeyConstraint(['advisor_org_id'], ['organizations.id'], name=op.f('fk_advisor_client_links_advisor_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['client_org_id'], ['organizations.id'], name=op.f('fk_advisor_client_links_client_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_advisor_client_links'))
    )
    op.create_index('ix_links_advisor', 'advisor_client_links', ['advisor_org_id', 'status'], unique=False)
    op.create_index('ix_links_client', 'advisor_client_links', ['client_org_id', 'status'], unique=False)
    op.create_index('uq_links_open_pair', 'advisor_client_links', ['advisor_org_id', 'client_org_id'], unique=True, postgresql_where="status <> 'revoked'")
    op.create_table('consents',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('version', sa.String(length=30), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("kind IN ('terms', 'data_processing', 'advisor_access', 'evaluation_data')", name=op.f('ck_consents_kind')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_consents_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_consents'))
    )
    op.create_index('ix_consents_org', 'consents', ['org_id', 'kind'], unique=False)
    op.create_table('email_outbox',
    sa.Column('to_user_id', sa.UUID(), nullable=False),
    sa.Column('template', sa.String(length=50), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['to_user_id'], ['users.id'], name=op.f('fk_email_outbox_to_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_outbox'))
    )
    op.create_table('email_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.String(length=20), nullable=False),
    sa.Column('token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("purpose IN ('verify_email', 'reset_password')", name=op.f('ck_email_tokens_purpose')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_email_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_email_tokens_token_hash'))
    )
    op.create_table('jobs',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('state', sa.String(length=10), server_default='queued', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default='5', nullable=False),
    sa.Column('idempotency_key', sa.String(length=200), nullable=True),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("state IN ('queued','running','succeeded','failed','parked')", name=op.f('ck_jobs_state')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_jobs_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs'))
    )
    op.create_index('ix_jobs_claim', 'jobs', ['state', 'run_after'], unique=False)
    op.create_index('ix_jobs_org', 'jobs', ['org_id', 'state'], unique=False)
    op.create_index('uq_jobs_idempotency', 'jobs', ['org_id', 'kind', 'idempotency_key'], unique=True, postgresql_where='idempotency_key IS NOT NULL')
    op.create_table('memberships',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'member', 'advisor', 'reviewer', 'platform_admin')", name=op.f('ck_memberships_role')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_memberships_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_memberships_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_memberships')),
    sa.UniqueConstraint('org_id', 'user_id', name='uq_memberships_org_user')
    )
    op.create_index('ix_memberships_user_id', 'memberships', ['user_id'], unique=False)
    op.create_table('sessions',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('csrf_token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('mfa_verified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_sessions_token_hash'))
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)
    op.execute(RLS_UP)



def downgrade() -> None:
    op.execute(RLS_DOWN)
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('ix_memberships_user_id', table_name='memberships')
    op.drop_table('memberships')
    op.drop_index('uq_jobs_idempotency', table_name='jobs', postgresql_where='idempotency_key IS NOT NULL')
    op.drop_index('ix_jobs_org', table_name='jobs')
    op.drop_index('ix_jobs_claim', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('email_tokens')
    op.drop_table('email_outbox')
    op.drop_index('ix_consents_org', table_name='consents')
    op.drop_table('consents')
    op.drop_index('uq_links_open_pair', table_name='advisor_client_links', postgresql_where="status <> 'revoked'")
    op.drop_index('ix_links_client', table_name='advisor_client_links')
    op.drop_index('ix_links_advisor', table_name='advisor_client_links')
    op.drop_table('advisor_client_links')
    op.drop_index('ix_grants_org_user', table_name='access_grants')
    op.drop_table('access_grants')
    op.drop_table('users')
    op.drop_table('rate_limit_counters')
    op.drop_table('organizations')
    op.drop_table('jurisdiction_policies')
    op.drop_index('ix_audit_target', table_name='audit_log')
    op.drop_index('ix_audit_org_seq', table_name='audit_log')
    op.drop_table('audit_log')

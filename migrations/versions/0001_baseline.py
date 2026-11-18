"""Baseline: helper schema, default privileges for the app role.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS compback")
    op.execute("GRANT USAGE ON SCHEMA compback TO compback_app")
    # Tables created later by the owner are usable by the app role (RLS still applies).
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO compback_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO compback_app"
    )
    # Helpers reading transaction-local tenant context. Empty string -> NULL (no access).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION compback.current_org_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('app.org_id', true), '')::uuid
        $$;
        CREATE OR REPLACE FUNCTION compback.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
        $$;
        CREATE OR REPLACE FUNCTION compback.current_actor_kind() RETURNS text
        LANGUAGE sql STABLE AS $$
          SELECT COALESCE(NULLIF(current_setting('app.actor_kind', true), ''), 'anonymous')
        $$;
        """
    )
    op.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA compback TO compback_app")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS compback CASCADE")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM compback_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM compback_app"
    )

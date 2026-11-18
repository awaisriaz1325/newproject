"""Allow the worker actor to append audit entries for any org (retention sweeps, ingestion).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY audit_insert ON audit_log")
    op.execute(
        """
        CREATE POLICY audit_insert ON audit_log FOR INSERT WITH CHECK (
          org_id IS NULL
          OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
          OR compback.is_auth_actor()
          OR compback.current_actor_kind() = 'worker')
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY audit_insert ON audit_log")
    op.execute(
        """
        CREATE POLICY audit_insert ON audit_log FOR INSERT WITH CHECK (
          org_id IS NULL
          OR (org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
          OR compback.is_auth_actor())
        """
    )

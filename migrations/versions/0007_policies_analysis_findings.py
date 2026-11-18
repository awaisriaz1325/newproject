"""policies analysis findings

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18 12:13:09.960916
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_UP = """
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
CREATE POLICY policies_rw ON policies FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
ALTER TABLE recomputations ENABLE ROW LEVEL SECURITY;
CREATE POLICY recomputations_rw ON recomputations FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY findings_rw ON findings FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
"""


def upgrade() -> None:
    op.create_table('policies',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('carrier_name', sa.String(length=200), nullable=False),
    sa.Column('policy_number', sa.String(length=60), nullable=False),
    sa.Column('state', sa.String(length=2), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_policies_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['state'], ['jurisdiction_policies.code'], name=op.f('fk_policies_state_jurisdiction_policies')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_policies'))
    )
    op.create_index('ix_policies_org', 'policies', ['org_id', 'period_start'], unique=False)
    op.create_table('recomputations',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=False),
    sa.Column('engine_version', sa.String(length=20), nullable=False),
    sa.Column('registry_version', sa.String(length=20), nullable=False),
    sa.Column('inputs_hash', sa.String(length=64), nullable=False),
    sa.Column('source_extraction_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('billed_total', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('recomputed_total', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('estimate_low', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('estimate_high', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_recomputations_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], name=op.f('fk_recomputations_policy_id_policies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recomputations'))
    )
    op.create_index('ix_recomputations_policy', 'recomputations', ['policy_id', 'created_at'], unique=False)
    op.create_table('findings',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=False),
    sa.Column('recomputation_id', sa.UUID(), nullable=False),
    sa.Column('detector', sa.String(length=40), nullable=False),
    sa.Column('rule_id', sa.String(length=40), nullable=False),
    sa.Column('rule_status', sa.String(length=12), nullable=False),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('impact_low', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('impact_high', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=False),
    sa.Column('priority_score', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
    sa.Column('customer_visible', sa.Boolean(), nullable=False),
    sa.Column('reviewer_status', sa.String(length=15), server_default='pending', nullable=False),
    sa.Column('reviewer_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("reviewer_status IN ('pending','confirmed','rejected','needs_expert')", name=op.f('ck_findings_reviewer_status')),
    sa.CheckConstraint('impact_low <= impact_high', name=op.f('ck_findings_impact_range')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_findings_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], name=op.f('fk_findings_policy_id_policies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recomputation_id'], ['recomputations.id'], name=op.f('fk_findings_recomputation_id_recomputations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_findings'))
    )
    op.create_index('ix_findings_org_status', 'findings', ['org_id', 'reviewer_status'], unique=False)
    op.create_index('ix_findings_recomputation', 'findings', ['recomputation_id'], unique=False)
    op.execute(RLS_UP)


def downgrade() -> None:
    op.drop_index('ix_findings_recomputation', table_name='findings')
    op.drop_index('ix_findings_org_status', table_name='findings')
    op.drop_table('findings')
    op.drop_index('ix_recomputations_policy', table_name='recomputations')
    op.drop_table('recomputations')
    op.drop_index('ix_policies_org', table_name='policies')
    op.drop_table('policies')

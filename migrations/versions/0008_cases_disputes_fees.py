"""cases disputes fees

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-18 12:20:13.174423
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_UP = """
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
CREATE POLICY cases_rw ON cases FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() IN ('worker', 'system'))
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() IN ('worker', 'system'));
ALTER TABLE case_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY case_events_rw ON case_events FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() IN ('worker', 'system'))
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() IN ('worker', 'system'));
ALTER TABLE dispute_packages ENABLE ROW LEVEL SECURITY;
CREATE POLICY dispute_packages_rw ON dispute_packages FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() IN ('worker', 'system'))
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() IN ('worker', 'system'));
ALTER TABLE outcomes ENABLE ROW LEVEL SECURITY;
CREATE POLICY outcomes_rw ON outcomes FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() IN ('worker', 'system'))
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() IN ('worker', 'system'));
ALTER TABLE fees ENABLE ROW LEVEL SECURITY;
CREATE POLICY fees_rw ON fees FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() IN ('worker', 'system'))
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() IN ('worker', 'system'));
-- Webhook idempotency keys only (no customer data): readable/writable by system actor.
ALTER TABLE stripe_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY stripe_events_system ON stripe_events FOR ALL
  USING (compback.current_actor_kind() = 'system')
  WITH CHECK (compback.current_actor_kind() = 'system');
"""


def upgrade() -> None:
    op.create_table('stripe_events',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('type', sa.String(length=100), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stripe_events'))
    )
    op.create_table('cases',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=False),
    sa.Column('recomputation_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=25), server_default='draft', nullable=False),
    sa.Column('submitter_mode', sa.String(length=30), nullable=False),
    sa.Column('deadline_date', sa.Date(), nullable=True),
    sa.Column('deadline_source', sa.Text(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('submitted_by', sa.UUID(), nullable=True),
    sa.Column('submission_method', sa.String(length=40), nullable=True),
    sa.Column('resolution', sa.String(length=20), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('draft','ready_for_review','approved_by_customer','submitted','carrier_responded','resolved','fee_invoiced','closed','withdrawn')", name=op.f('ck_cases_status')),
    sa.CheckConstraint('deadline_date IS NULL OR deadline_source IS NOT NULL', name=op.f('ck_cases_deadline_needs_source')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_cases_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], name=op.f('fk_cases_policy_id_policies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recomputation_id'], ['recomputations.id'], name=op.f('fk_cases_recomputation_id_recomputations')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cases'))
    )
    op.create_index('ix_cases_org_status', 'cases', ['org_id', 'status'], unique=False)
    op.create_table('case_events',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('from_status', sa.String(length=25), nullable=True),
    sa.Column('to_status', sa.String(length=25), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_case_events_case_id_cases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_case_events_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_events'))
    )
    op.create_index('ix_case_events_case', 'case_events', ['case_id', 'created_at'], unique=False)
    op.create_table('dispute_packages',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('finding_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('total_low', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_high', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('pdf_key', sa.String(length=300), nullable=False),
    sa.Column('docx_key', sa.String(length=300), nullable=False),
    sa.Column('approved_by', sa.UUID(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_dispute_packages_case_id_cases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_dispute_packages_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dispute_packages')),
    sa.UniqueConstraint('case_id', 'version', name='uq_dispute_packages_case_ver')
    )
    op.create_table('fees',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('basis_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('rate', sa.Numeric(precision=6, scale=4), nullable=True),
    sa.Column('credit_applied', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
    sa.Column('cap', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('calculation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), server_default='draft', nullable=False),
    sa.Column('stripe_invoice_id', sa.String(length=100), nullable=True),
    sa.Column('hosted_invoice_url', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('analysis','contingency')", name=op.f('ck_fees_kind')),
    sa.CheckConstraint("status IN ('draft','invoiced','paid','void','refunded','disputed')", name=op.f('ck_fees_status')),
    sa.CheckConstraint('amount >= 0', name=op.f('ck_fees_amount_nonneg')),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_fees_case_id_cases'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_fees_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fees')),
    sa.UniqueConstraint('stripe_invoice_id', name=op.f('uq_fees_stripe_invoice_id'))
    )
    op.create_index('ix_fees_org', 'fees', ['org_id', 'status'], unique=False)
    op.create_index('uq_fees_case_kind', 'fees', ['case_id', 'kind'], unique=True, postgresql_where="status <> 'void'")
    op.create_table('outcomes',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('received_on', sa.Date(), nullable=True),
    sa.Column('proof_document_id', sa.UUID(), nullable=True),
    sa.Column('recorded_by', sa.UUID(), nullable=False),
    sa.Column('verified_by', sa.UUID(), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("kind IN ('refund','credit','denied','partial')", name=op.f('ck_outcomes_kind')),
    sa.CheckConstraint('amount >= 0', name=op.f('ck_outcomes_amount_nonneg')),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name=op.f('fk_outcomes_case_id_cases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_outcomes_org_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['proof_document_id'], ['documents.id'], name=op.f('fk_outcomes_proof_document_id_documents')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outcomes'))
    )
    op.create_index('ix_outcomes_case', 'outcomes', ['case_id'], unique=False)
    op.add_column("organizations", sa.Column("billing_customer_id", sa.String(length=100), nullable=True))
    op.execute(RLS_UP)


def downgrade() -> None:
    op.drop_column("organizations", "billing_customer_id")
    op.drop_index('ix_outcomes_case', table_name='outcomes')
    op.drop_table('outcomes')
    op.drop_index('uq_fees_case_kind', table_name='fees', postgresql_where="status <> 'void'")
    op.drop_index('ix_fees_org', table_name='fees')
    op.drop_table('fees')
    op.drop_table('dispute_packages')
    op.drop_index('ix_case_events_case', table_name='case_events')
    op.drop_table('case_events')
    op.drop_index('ix_cases_org_status', table_name='cases')
    op.drop_table('cases')
    op.drop_table('stripe_events')

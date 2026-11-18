"""extractions

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-18 12:04:40.849532
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_UP = """
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
CREATE POLICY extractions_rw ON extractions FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
ALTER TABLE extraction_edits ENABLE ROW LEVEL SECURITY;
CREATE POLICY extraction_edits_rw ON extraction_edits FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
"""


def upgrade() -> None:
    op.create_table('extractions',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('doc_type', sa.String(length=40), nullable=False),
    sa.Column('schema_name', sa.String(length=60), nullable=False),
    sa.Column('schema_version', sa.String(length=30), nullable=False),
    sa.Column('extractor', sa.String(length=60), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('issues', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('review_reasons', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('status', sa.String(length=15), nullable=False),
    sa.Column('min_confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('llm_input_tokens', sa.Integer(), server_default='0', nullable=False),
    sa.Column('llm_output_tokens', sa.Integer(), server_default='0', nullable=False),
    sa.Column('llm_cost_usd', sa.Numeric(precision=10, scale=4), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('verified_by', sa.UUID(), nullable=True),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("status IN ('needs_review','ready','verified','failed')", name=op.f('ck_extractions_status')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_extractions_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_extractions_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_extractions'))
    )
    op.create_index('ix_extractions_doc', 'extractions', ['document_id', 'created_at'], unique=False)
    op.create_index('ix_extractions_org', 'extractions', ['org_id'], unique=False)
    op.create_table('extraction_edits',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('extraction_id', sa.UUID(), nullable=False),
    sa.Column('field_path', sa.String(length=120), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('edited_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['extraction_id'], ['extractions.id'], name=op.f('fk_extraction_edits_extraction_id_extractions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_extraction_edits_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_extraction_edits'))
    )
    op.create_index('ix_extraction_edits_ext', 'extraction_edits', ['extraction_id'], unique=False)
    op.execute(RLS_UP)


def downgrade() -> None:
    op.drop_index('ix_extraction_edits_ext', table_name='extraction_edits')
    op.drop_table('extraction_edits')
    op.drop_index('ix_extractions_org', table_name='extractions')
    op.drop_index('ix_extractions_doc', table_name='extractions')
    op.drop_table('extractions')

"""document vault

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-18 11:52:44.838684
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Documents: tenant access, plus the worker (cross-org retention sweeps, ingestion).
RLS_UP = """
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY documents_rw ON documents FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');

ALTER TABLE document_pages ENABLE ROW LEVEL SECURITY;
CREATE POLICY document_pages_rw ON document_pages FOR ALL
  USING ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
         OR compback.current_actor_kind() = 'worker')
  WITH CHECK ((org_id = compback.current_org_id() AND (SELECT compback.org_access_ok()))
              OR compback.current_actor_kind() = 'worker');
"""


def upgrade() -> None:
    op.create_table('documents',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=True),
    sa.Column('doc_type', sa.String(length=40), server_default='unknown', nullable=False),
    sa.Column('file_kind', sa.String(length=10), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('storage_key', sa.String(length=300), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=12), server_default='uploaded', nullable=False),
    sa.Column('malware_status', sa.String(length=10), server_default='pending', nullable=False),
    sa.Column('redaction_count', sa.Integer(), nullable=True),
    sa.Column('rejection_code', sa.String(length=40), nullable=True),
    sa.Column('rejection_message', sa.Text(), nullable=True),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('upload_source', sa.String(length=20), server_default='web', nullable=False),
    sa.Column('uploaded_by', sa.UUID(), nullable=False),
    sa.Column('retention_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("malware_status IN ('pending','clean','infected','error')", name=op.f('ck_documents_malware_status')),
    sa.CheckConstraint("status IN ('uploaded','processing','ready','rejected','deleted')", name=op.f('ck_documents_status')),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_documents_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents'))
    )
    op.create_index('ix_documents_org_created', 'documents', ['org_id', 'created_at'], unique=False)
    op.create_index('ix_documents_retention', 'documents', ['retention_until'], unique=False)
    op.create_index('uq_documents_org_sha', 'documents', ['org_id', 'sha256'], unique=True, postgresql_where='deleted_at IS NULL')
    op.create_table('document_pages',
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('page_no', sa.Integer(), nullable=False),
    sa.Column('text_source', sa.String(length=10), nullable=False),
    sa.Column('text_enc', sa.LargeBinary(), nullable=False),
    sa.Column('ocr_confidence', sa.Numeric(precision=5, scale=1), nullable=True),
    sa.Column('redactions', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('quality_flags', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('image_key', sa.String(length=300), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_pages_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], name=op.f('fk_document_pages_org_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_pages')),
    sa.UniqueConstraint('document_id', 'page_no', name='uq_document_pages_doc_page')
    )
    op.create_index('ix_document_pages_org', 'document_pages', ['org_id'], unique=False)
    op.execute(RLS_UP)


def downgrade() -> None:
    op.drop_index('ix_document_pages_org', table_name='document_pages')
    op.drop_table('document_pages')
    op.drop_index('uq_documents_org_sha', table_name='documents', postgresql_where='deleted_at IS NULL')
    op.drop_index('ix_documents_retention', table_name='documents')
    op.drop_index('ix_documents_org_created', table_name='documents')
    op.drop_table('documents')

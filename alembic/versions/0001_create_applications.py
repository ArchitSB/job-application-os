"""create applications

Revision ID: 0001
Revises: 
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('applications',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('normalized_company_name', sa.String(length=255), nullable=False),
    sa.Column('role_title', sa.String(length=255), nullable=False),
    sa.Column('normalized_role_title', sa.String(length=255), nullable=False),
    sa.Column('job_url', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('application_method', sa.Enum('email', 'portal', 'platform', 'other', name='application_method', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('resume_type', sa.Enum('technical', 'product', name='resume_type', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('contact_name', sa.String(length=255), nullable=True),
    sa.Column('contact_email', sa.String(length=320), nullable=True),
    sa.Column('date_found', sa.DateTime(timezone=True), nullable=True),
    sa.Column('date_applied', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('discovered', 'shortlisted', 'approved', 'prepared', 'applied', 'awaiting_response', 'interview', 'rejected', 'withdrawn', 'offer', 'skipped', name='application_status', native_enum=False, create_constraint=True), server_default='discovered', nullable=False),
    sa.Column('email_subject', sa.Text(), nullable=True),
    sa.Column('email_body', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_applications'))
    )
    op.create_index('ix_applications_normalized_company_role', 'applications', ['normalized_company_name', 'normalized_role_title'], unique=False)
    op.create_index('ix_applications_normalized_role_title', 'applications', ['normalized_role_title'], unique=False)
    # Maintain timestamps for every writer, including direct SQL clients.
    op.execute("""
        CREATE FUNCTION public.set_applications_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER applications_updated_at
        BEFORE UPDATE ON public.applications
        FOR EACH ROW EXECUTE FUNCTION public.set_applications_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER applications_updated_at ON public.applications")
    op.execute("DROP FUNCTION public.set_applications_updated_at()")
    op.drop_index('ix_applications_normalized_role_title', table_name='applications')
    op.drop_index('ix_applications_normalized_company_role', table_name='applications')
    op.drop_table('applications')

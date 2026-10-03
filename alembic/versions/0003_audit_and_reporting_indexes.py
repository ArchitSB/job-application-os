"""Protect audit events and index reporting filters.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_applications_date_applied", "applications", ["date_applied"])
    op.create_index("ix_applications_resume_type", "applications", ["resume_type"])
    op.create_index("ix_job_leads_recommended_resume_type", "job_leads", ["recommended_resume_type"])
    op.execute("""
        CREATE FUNCTION public.protect_application_events() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Application events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER application_events_append_only
        BEFORE UPDATE OR DELETE ON public.application_events
        FOR EACH ROW EXECUTE FUNCTION public.protect_application_events()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER application_events_append_only ON public.application_events")
    op.execute("DROP FUNCTION public.protect_application_events()")
    op.drop_index("ix_job_leads_recommended_resume_type", table_name="job_leads")
    op.drop_index("ix_applications_resume_type", table_name="applications")
    op.drop_index("ix_applications_date_applied", table_name="applications")

"""Preserve structured research and index canonical job identities.

Revision ID: 0004
Revises: 0003
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def url_key(value):
    # Frozen copy of v1 identity normalization; migrations do not import application code.
    parts = urlsplit(value.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}
    ]
    host = (parts.hostname or "").casefold()
    if parts.port and parts.port not in (80, 443):
        host += f":{parts.port}"
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))


def upgrade():
    op.add_column("job_leads", sa.Column("research", postgresql.JSONB(), nullable=True))
    op.add_column(
        "job_leads",
        sa.Column(
            "identity_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    leads = sa.table(
        "job_leads",
        sa.column("id", sa.Uuid()),
        sa.column("job_url", sa.Text()),
        sa.column("application_url", sa.Text()),
        sa.column("identity_urls", postgresql.ARRAY(sa.Text())),
    )
    connection = op.get_bind()
    for row in connection.execute(sa.select(leads).execution_options(yield_per=100)):
        keys = sorted({url_key(url) for url in (row.job_url, row.application_url) if url})
        connection.execute(leads.update().where(leads.c.id == row.id).values(identity_urls=keys))
    op.create_index("ix_job_leads_identity_urls", "job_leads", ["identity_urls"], postgresql_using="gin")


def downgrade():
    op.drop_index("ix_job_leads_identity_urls", table_name="job_leads")
    op.drop_column("job_leads", "identity_urls")
    op.drop_column("job_leads", "research")

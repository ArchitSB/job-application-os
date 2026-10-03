import os

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 with a migrated PostgreSQL database"
    ),
]


def test_postgresql_connection_and_migration():
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert int(connection.execute(text("SHOW server_version_num")).scalar_one()) >= 180000
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        indexes = {index["name"] for index in inspect(connection).get_indexes("applications")}
        assert "ix_applications_normalized_company_role" in indexes
        assert "ix_applications_normalized_role_title" in indexes


def test_defaults_constraints_duplicate_lookup_and_update_trigger():
    # Always roll back: no test records persist in the development database.
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            insert = text("""
                INSERT INTO applications (
                    company_name, normalized_company_name, role_title,
                    normalized_role_title, source, application_method, resume_type
                ) VALUES ('Test Company', 'test company', 'Engineer', 'engineer',
                          'other', 'portal', 'technical')
                RETURNING id, status, created_at, updated_at
            """)
            first = connection.execute(insert).mappings().one()
            second = connection.execute(insert).mappings().one()
            assert first["id"] != second["id"]
            assert first["status"] == "discovered"
            assert first["created_at"].tzinfo is not None
            updated = connection.execute(
                text("UPDATE applications SET notes = 'changed' WHERE id = :id RETURNING updated_at"),
                {"id": first["id"]},
            ).scalar_one()
            assert updated > first["updated_at"]
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text("UPDATE applications SET status = 'invalid' WHERE id = :id"), {"id": first["id"]}
                    )
        finally:
            transaction.rollback()

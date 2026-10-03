from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/test_unused")
    get_settings.cache_clear()
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()
    get_settings.cache_clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health(client):
    session = Mock()
    session.execute.return_value.scalar_one.return_value = 1
    client.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_database_failure_is_sanitized(client):
    session = Mock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private driver details"))
    client.app.dependency_overrides[get_session] = lambda: session
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "http_503", "message": "Database unavailable"}}

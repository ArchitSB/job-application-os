import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dotenv_loading_and_environment_override(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "APP_NAME", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://localhost/config_test\nAPP_NAME=From dotenv\nENVIRONMENT=test\n"
    )
    settings = Settings(_env_file=env_file)
    assert settings.app_name == "From dotenv"
    assert settings.environment == "test"
    assert settings.database_url.get_secret_value().endswith("/config_test")
    assert "postgresql" not in repr(settings)
    monkeypatch.setenv("APP_NAME", "Environment override")
    assert Settings(_env_file=env_file).app_name == "Environment override"


def test_database_url_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_wrong_driver_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///unsupported.db")

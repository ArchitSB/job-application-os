from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC -c statement_timeout=5000"},
        hide_parameters=True,
    )


def get_session() -> Iterator[Session]:
    # Callers explicitly commit successful writes; closing rolls back unfinished work.
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session

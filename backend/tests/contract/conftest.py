from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

import appfit.models  # noqa: F401 - registers every table on Base.metadata
from appfit.db.base import Base


def _truncate(engine: Engine) -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Real commits instead of one rolled-back transaction: thousands of fuzzed requests exhaust its locks."""
    _truncate(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    _truncate(engine)

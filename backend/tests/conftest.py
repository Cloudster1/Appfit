import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from appfit.auth.security import create_access_token
from appfit.bootstrap import create_user
from appfit.config import Settings
from appfit.main import create_app
from appfit.ml.fake_embedder import FakeEmbedder
from appfit.models import Role, User
from appfit.worker import EmbeddingWorker

BACKEND_DIR = Path(__file__).resolve().parents[1]
PG_IMAGE = "pgvector/pgvector:pg17"
TEST_PASSWORD = "correct-horse-battery"
WORKER_BATCH = 64
WORKER_POLL_SECONDS = 0.1


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """TEST_DATABASE_URL if set (must be a dedicated, disposable DB), else a throwaway testcontainer."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(PG_IMAGE, driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    cfg.attributes["configure_logging"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = create_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture
def session_factory(connection: Connection) -> sessionmaker[Session]:
    return sessionmaker(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=database_url,
        jwt_secret="test-secret-with-enough-length-0123456789",
        embedding_backend="fake",
        embed_worker_enabled=False,
        bootstrap_admin_email=None,
        bootstrap_admin_password=None,
    )


@pytest.fixture
def app(settings: Settings, session_factory: sessionmaker[Session], embedder: FakeEmbedder) -> FastAPI:
    return create_app(settings, session_factory, embedder, start_background=False)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, headers={"X-Requested-With": "XMLHttpRequest"}) as c:
        yield c


@pytest.fixture
def users(db: Session) -> dict[Role, User]:
    out = {}
    for role in Role:
        out[role] = create_user(
            db, f"{role.value}-{uuid.uuid4().hex[:6]}@example.local", TEST_PASSWORD, role.value.title(), role
        )
    db.commit()
    return out


@pytest.fixture
def auth(users: dict[Role, User], settings: Settings) -> Callable[[Role], dict[str, str]]:
    def headers(role: Role) -> dict[str, str]:
        user = users[role]
        return {"Authorization": f"Bearer {create_access_token(user.id, role.value, settings)}"}

    return headers


@pytest.fixture
def run_worker(session_factory: sessionmaker[Session], embedder: FakeEmbedder, database_url: str) -> Callable[[], int]:
    worker = EmbeddingWorker(session_factory, embedder, database_url, WORKER_BATCH, WORKER_POLL_SECONDS)
    return worker.run_once

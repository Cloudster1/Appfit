import logging
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from appfit import __version__
from appfit.api.routers import (
    admin,
    apps,
    auth,
    health,
    imports,
    interfaces,
    maintainers,
    meta,
    search,
    tags,
    users,
)
from appfit.bootstrap import bootstrap_admin
from appfit.config import EMBEDDING_DIM, Settings, get_settings
from appfit.db.engine import make_engine, make_session_factory
from appfit.ml.embedder import Embedder, build_embedder
from appfit.services.errors import ServiceError
from appfit.worker import EmbeddingWorker

log = logging.getLogger("appfit")

API_PREFIX = "/api"
CSRF_HEADER = "x-requested-with"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
WARMUP_TEXT = "warm up"
# Hugging Face hub clients log every HTTP request at INFO.
NOISY_LOGGERS = ("httpx", "huggingface_hub", "urllib3")


def _start_worker(app: FastAPI, embedder: Embedder) -> None:
    settings: Settings = app.state.settings
    if not settings.embed_worker_enabled:
        return
    worker = EmbeddingWorker(
        app.state.session_factory,
        embedder,
        settings.database_url,
        settings.embed_worker_batch_size,
        settings.embed_worker_poll_seconds,
    )
    thread = threading.Thread(target=worker.run_forever, args=(app.state.stop_event,), daemon=True, name="embed-worker")
    app.state.worker, app.state.worker_thread = worker, thread
    thread.start()


def _load_model(app: FastAPI) -> None:
    try:
        embedder = build_embedder(app.state.settings)
        if embedder.dim != EMBEDDING_DIM:
            raise RuntimeError(
                f"Model dimension {embedder.dim} does not match the database ({EMBEDDING_DIM}); a migration is required"
            )
        embedder.embed_queries([WARMUP_TEXT])
    except Exception as exc:
        log.exception("Embedding model failed to load")
        app.state.embedder_error = str(exc)
        return
    app.state.embedder = embedder
    log.info("Embedding model ready: %s", embedder.model_id)
    _start_worker(app, embedder)


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    embedder: Embedder | None = None,
    start_background: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    for noisy in NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        bootstrap_admin(app.state.session_factory, settings)
        if start_background:
            if app.state.embedder is None:
                threading.Thread(target=_load_model, args=(app,), daemon=True, name="model-loader").start()
            else:
                _start_worker(app, app.state.embedder)
        yield
        app.state.stop_event.set()

    app = FastAPI(
        title="Appfit API",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=f"{API_PREFIX}/docs/oauth2-redirect",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory or make_session_factory(make_engine(settings.database_url))
    app.state.embedder = embedder
    app.state.embedder_error = None
    app.state.worker = None
    app.state.worker_thread = None
    app.state.stop_event = threading.Event()

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Cookie-authenticated writes must carry X-Requested-With; bearer clients are exempt."""
        if (
            request.method not in SAFE_METHODS
            and request.url.path.startswith(API_PREFIX)
            and not request.headers.get("authorization", "").lower().startswith("bearer ")
            and not request.headers.get(CSRF_HEADER)
        ):
            return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=HTTPStatus.FORBIDDEN)
        return await call_next(request)

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=int(exc.status_code))

    for module in (health, auth, users, apps, interfaces, tags, maintainers, search, imports, admin, meta):
        app.include_router(module.router, prefix=API_PREFIX)
    return app

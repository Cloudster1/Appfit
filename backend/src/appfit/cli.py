import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import func, select

from appfit.config import DB_WAIT_INTERVAL_SECONDS, DB_WAIT_TIMEOUT_SECONDS, get_settings
from appfit.db.engine import make_engine, make_session_factory
from appfit.models import Role, User

app = typer.Typer(help="Appfit administration commands", no_args_is_help=True)


def _session_factory():
    return make_session_factory(make_engine(get_settings().database_url))


@app.command("create-admin")
def create_admin(
    email: Annotated[str, typer.Option(prompt=True)],
    password: Annotated[str, typer.Option(prompt=True, hide_input=True, confirmation_prompt=True)],
    name: str = "Administrator",
    role: Role = Role.admin,
) -> None:
    """Create a user (admin by default)."""
    from appfit.bootstrap import create_user

    with _session_factory()() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == email.lower())) is not None:
            typer.echo(f"User {email} already exists", err=True)
            raise typer.Exit(1)
        create_user(db, email, password, name, role)
        db.commit()
    typer.echo(f"Created {role.value} {email}")


@app.command()
def seed(
    file: Path,
    dry_run: bool = False,
    mode: Annotated[str, typer.Option(help="upsert or create_only")] = "upsert",
) -> None:
    """Import a JSON or CSV catalog file (same semantics as the import API)."""
    from appfit.services.importer.parse_csv import parse_csv
    from appfit.services.importer.parse_json import parse_json
    from appfit.services.importer.upsert import run_import

    content = file.read_bytes()
    fmt = "json" if file.suffix.lower() == ".json" else "csv"
    rows, warnings = parse_json(content) if fmt == "json" else parse_csv(content)
    with _session_factory()() as db:
        report = run_import(
            db,
            rows,
            fmt=fmt,
            mode="create_only" if mode == "create_only" else "upsert",
            dry_run=dry_run,
            skip_invalid=False,
            user_id=None,
            filename=file.name,
            parse_warnings=warnings,
        )
        db.commit()
    typer.echo(report.stats.model_dump_json())
    for err in report.errors:
        typer.echo(f"row {err.row} {err.slug or ''} {err.field or ''}: {err.message}", err=True)
    if report.errors:
        raise typer.Exit(1)


@app.command("download-model")
def download_model() -> None:
    """Download (and cache) the configured embedding model, then run one test encoding."""
    from appfit.ml.embedder import build_embedder

    embedder = build_embedder(get_settings())
    vec = embedder.embed_queries(["Appfit model check"])
    typer.echo(f"{embedder.model_id}: dim={vec.shape[1]}")


@app.command()
def reembed(
    all_rows: Annotated[bool, typer.Option("--all", help="Re-embed everything, not only stale rows")] = False,
) -> None:
    """Embed stale rows now (or everything with --all) in the foreground."""
    from appfit.ml.embedder import build_embedder
    from appfit.services.embedding_sync import mark_all_stale
    from appfit.worker import EmbeddingWorker

    settings = get_settings()
    factory = _session_factory()
    if all_rows:
        with factory() as db:
            mark_all_stale(db)
            db.commit()
    worker = EmbeddingWorker(
        factory,
        build_embedder(settings),
        settings.database_url,
        settings.embed_worker_batch_size,
        settings.embed_worker_poll_seconds,
    )
    typer.echo(f"Embedded {worker.run_once()} rows with {worker.embedder.model_id}")


@app.command("wait-for-db")
def wait_for_db(timeout: float = DB_WAIT_TIMEOUT_SECONDS) -> None:
    """Wait until the database accepts connections; for container startup."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    engine = make_engine(get_settings().database_url)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            if time.monotonic() > deadline:
                typer.echo(f"Database not reachable after {timeout:.0f}s: {exc.orig}", err=True)
                raise typer.Exit(1) from None
            typer.echo("Waiting for the database ...", err=True)
            time.sleep(DB_WAIT_INTERVAL_SECONDS)
        finally:
            engine.dispose()


@app.command()
def worker() -> None:
    """Run the embedding worker as a standalone process."""
    from appfit.ml.embedder import build_embedder
    from appfit.worker import EmbeddingWorker

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    w = EmbeddingWorker(
        _session_factory(),
        build_embedder(settings),
        settings.database_url,
        settings.embed_worker_batch_size,
        settings.embed_worker_poll_seconds,
    )
    stop = threading.Event()
    try:
        w.run_forever(stop)
    except KeyboardInterrupt:
        stop.set()


@app.command("eval")
def evaluate(
    queries: Path = Path("eval/queries.yaml"),
    pairs: Path = Path("eval/pair_labels.yaml"),
    sweep: bool = False,
    report: Path | None = None,
) -> None:
    """Retrieval metrics on labelled queries; --sweep suggests calibrated thresholds."""
    from appfit.evaluation import run_evaluation

    result = run_evaluation(queries, pairs, sweep=sweep)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    sys.stdout.write(text + "\n")


if __name__ == "__main__":
    app()

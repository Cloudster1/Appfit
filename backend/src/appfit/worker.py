import logging
import threading

import psycopg
from sqlalchemy.orm import Session, sessionmaker

from appfit.db.engine import libpq_url
from appfit.ml.embedder import Embedder
from appfit.services.apps import EMBED_CHANNEL
from appfit.services.embedding_sync import embed_stale_apps, embed_stale_capabilities, embed_stale_interfaces

log = logging.getLogger(__name__)


class EmbeddingWorker:
    """Embeds stale apps, capabilities and interfaces; wakes on NOTIFY or every poll interval."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedder: Embedder,
        database_url: str,
        batch_size: int,
        poll_seconds: float,
    ) -> None:
        self.session_factory = session_factory
        self.embedder = embedder
        self.database_url = database_url
        self.batch_size = batch_size
        self.poll_seconds = poll_seconds
        self.last_error: str | None = None

    def run_once(self) -> int:
        """Process stale rows until none are left; returns the number of rows embedded."""
        total = 0
        while True:
            with self.session_factory() as db:
                n = embed_stale_apps(db, self.embedder, self.batch_size)
                n += embed_stale_capabilities(db, self.embedder, self.batch_size)
                n += embed_stale_interfaces(db, self.embedder, self.batch_size)
                db.commit()
            total += n
            if n == 0:
                return total

    def _wait_for_notify(self, conn: psycopg.Connection | None, stop: threading.Event) -> None:
        if conn is None:
            stop.wait(self.poll_seconds)
            return
        for _ in conn.notifies(timeout=self.poll_seconds, stop_after=1):
            break

    def _listen(self) -> psycopg.Connection | None:
        try:
            conn = psycopg.connect(libpq_url(self.database_url), autocommit=True)
            conn.execute(f"LISTEN {EMBED_CHANNEL}")
            return conn
        except psycopg.Error as exc:
            log.warning("LISTEN unavailable, falling back to polling: %s", exc)
            return None

    def run_forever(self, stop: threading.Event) -> None:
        log.info("Embedding worker started (model=%s)", self.embedder.model_id)
        conn = self._listen()
        try:
            while not stop.is_set():
                try:
                    n = self.run_once()
                    if n:
                        log.info("Embedded %d rows", n)
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                    log.exception("Embedding run failed")
                    stop.wait(self.poll_seconds)
                    continue
                try:
                    self._wait_for_notify(conn, stop)
                except psycopg.Error:
                    log.warning("LISTEN connection lost, reconnecting")
                    conn = self._listen()
                    stop.wait(self.poll_seconds)
        finally:
            if conn is not None:
                conn.close()
        log.info("Embedding worker stopped")

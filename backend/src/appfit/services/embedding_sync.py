import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from appfit.ml.embedder import Embedder
from appfit.models import App, AppCapability, Interface
from appfit.services.apps import summary_document
from appfit.services.interface_docs import embedded_texts, side_text
from appfit.text import content_hash

log = logging.getLogger(__name__)


@dataclass
class EmbeddingCounts:
    apps_total: int
    apps_indexed: int
    capabilities_total: int
    capabilities_indexed: int
    interfaces_total: int = 0
    interfaces_indexed: int = 0

    @property
    def pending(self) -> int:
        return (
            (self.apps_total - self.apps_indexed)
            + (self.capabilities_total - self.capabilities_indexed)
            + (self.interfaces_total - self.interfaces_indexed)
        )


def _stale_app_filter(model_id: str):
    return or_(App.embedded_at.is_(None), App.embedding_model.is_distinct_from(model_id))


def _stale_cap_filter(model_id: str):
    return or_(AppCapability.embedded_at.is_(None), AppCapability.embedding_model.is_distinct_from(model_id))


def _stale_iface_filter(model_id: str):
    return or_(Interface.embedded_at.is_(None), Interface.embedding_model.is_distinct_from(model_id))


def _keep_updated_at(row: App | Interface) -> None:
    """Embedding is not an edit: SET updated_at = updated_at stops onupdate from bumping it."""
    row.updated_at = type(row).updated_at


def embed_stale_apps(db: Session, embedder: Embedder, batch_size: int) -> int:
    apps = db.scalars(
        select(App)
        .where(_stale_app_filter(embedder.model_id))
        .order_by(App.updated_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True, of=App)
        .options(selectinload(App.tags))
    ).all()
    if not apps:
        return 0
    docs = [summary_document(a) for a in apps]
    vectors = embedder.embed_passages(docs)
    now = datetime.now(UTC)
    for app, doc, vec in zip(apps, docs, vectors, strict=True):
        app.summary_embedding = vec
        app.summary_hash = content_hash(doc)
        app.embedding_model = embedder.model_id
        app.embedded_at = now
        _keep_updated_at(app)
    return len(apps)


def embed_stale_capabilities(db: Session, embedder: Embedder, batch_size: int) -> int:
    caps = db.scalars(
        select(AppCapability)
        .where(_stale_cap_filter(embedder.model_id))
        .order_by(AppCapability.app_id, AppCapability.position)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    if not caps:
        return 0
    vectors = embedder.embed_passages([c.text for c in caps])
    now = datetime.now(UTC)
    for cap, vec in zip(caps, vectors, strict=True):
        cap.embedding = vec
        cap.content_hash = content_hash(cap.text)
        cap.embedding_model = embedder.model_id
        cap.embedded_at = now
    return len(caps)


def embed_stale_interfaces(db: Session, embedder: Embedder, batch_size: int) -> int:
    ifaces = (
        db.scalars(
            select(Interface)
            .where(_stale_iface_filter(embedder.model_id))
            .order_by(Interface.updated_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True, of=Interface)
        )
        .unique()
        .all()
    )
    if not ifaces:
        return 0
    jobs = [(i, side, text) for i in ifaces for side in ("from", "to") if (text := side_text(i, side)) is not None]
    vectors = embedder.embed_passages([text for _, _, text in jobs])
    for (iface, side, _), vec in zip(jobs, vectors, strict=True):
        setattr(iface, f"{side}_embedding", vec)
    now = datetime.now(UTC)
    for iface in ifaces:
        iface.content_hash = content_hash(embedded_texts(iface))
        iface.embedding_model = embedder.model_id
        iface.embedded_at = now
        _keep_updated_at(iface)
    return len(ifaces)


def embedding_counts(db: Session, model_id: str) -> EmbeddingCounts:
    apps_total = db.scalar(select(func.count()).select_from(App)) or 0
    apps_stale = db.scalar(select(func.count()).select_from(App).where(_stale_app_filter(model_id))) or 0
    caps_total = db.scalar(select(func.count()).select_from(AppCapability)) or 0
    caps_stale = db.scalar(select(func.count()).select_from(AppCapability).where(_stale_cap_filter(model_id))) or 0
    if_total = db.scalar(select(func.count()).select_from(Interface)) or 0
    if_stale = db.scalar(select(func.count()).select_from(Interface).where(_stale_iface_filter(model_id))) or 0
    return EmbeddingCounts(
        apps_total, apps_total - apps_stale, caps_total, caps_total - caps_stale, if_total, if_total - if_stale
    )


def mark_all_stale(db: Session) -> None:
    db.execute(update(App).values(embedded_at=None, updated_at=App.updated_at))
    db.execute(update(AppCapability).values(embedded_at=None))
    db.execute(update(Interface).values(embedded_at=None, updated_at=Interface.updated_at))

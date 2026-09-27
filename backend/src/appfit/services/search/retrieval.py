import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy import ColumnElement, cast, func, literal, or_, select, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session, undefer

from appfit.config import HNSW_EF_SEARCH
from appfit.models import (
    App,
    AppCapability,
    AppMaintainer,
    Interface,
    InterfaceStatus,
    LicenseType,
    LifecycleStatus,
    Maintainer,
    Tag,
)
from appfit.services.apps import in_any_domain
from appfit.services.interface_docs import interface_document, to_summary
from appfit.text import stem_map

from .scoring import CandCap, Candidate

_TS_RANK_SCALE_TO_UNIT = 32  # ts_rank normalization flag: rank / (rank + 1)


@dataclass
class FilterSpec:
    lifecycle: list[LifecycleStatus] | None = None
    tags: list[str] = field(default_factory=list)
    license_types: list[LicenseType] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    maintainer: str | None = None


def filter_conditions(f: FilterSpec) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = []
    if f.lifecycle:
        conds.append(App.lifecycle_status.in_(f.lifecycle))
    else:
        conds.append(App.lifecycle_status != LifecycleStatus.retired)
    for tag in f.tags:
        conds.append(App.tags.any(Tag.name == tag.strip().lower()))
    if f.license_types:
        conds.append(App.license_type.in_(f.license_types))
    if f.domains:
        conds.append(in_any_domain(f.domains))
    if f.maintainer:
        like = f"%{f.maintainer.strip()}%"
        conds.append(
            App.maintainer_links.any(
                AppMaintainer.maintainer.has(or_(Maintainer.name.ilike(like), Maintainer.email.ilike(like)))
            )
        )
    return conds


def configure_vector_search(db: Session) -> None:
    """Per-transaction HNSW settings; iterative scans keep filtered queries from coming back short."""
    db.execute(text(f"SET LOCAL hnsw.ef_search = {int(HNSW_EF_SEARCH)}"))
    db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))


def summary_ranking(
    db: Session, query_vec: np.ndarray, conds: list[ColumnElement[bool]], model_id: str, limit: int
) -> list[uuid.UUID]:
    dist = App.summary_embedding.cosine_distance(query_vec).label("dist")
    rows = db.execute(
        select(App.id, dist)
        .where(*conds, App.summary_embedding.is_not(None), App.embedding_model == model_id)
        .order_by(dist)
        .limit(limit)
    ).all()
    return [r.id for r in sorted(rows, key=lambda r: r.dist)]


def _interface_hits(
    db: Session, vec: np.ndarray, conds: list[ColumnElement[bool]], model_id: str, limit: int
) -> list[tuple[uuid.UUID, float]]:
    """(app id, similarity) for the closest interface sides of apps passing the filters.

    Each side's vector speaks for the app at that end."""
    hits: list[tuple[uuid.UUID, float]] = []
    for side in ("from", "to"):
        column = getattr(Interface, f"{side}_embedding")
        app_col = getattr(Interface, f"{side}_app_id")
        dist = column.cosine_distance(vec).label("dist")
        rows = db.execute(
            select(app_col.label("app_id"), dist)
            .join(App, App.id == app_col)
            .where(
                *conds,
                column.is_not(None),
                Interface.embedding_model == model_id,
                Interface.status != InterfaceStatus.deprecated,
            )
            .order_by(dist)
            .limit(limit)
        ).all()
        hits += [(r.app_id, 1.0 - float(r.dist)) for r in rows]
    return hits


def capability_ranking(
    db: Session,
    req_vecs: np.ndarray,
    weights: list[float],
    conds: list[ColumnElement[bool]],
    model_id: str,
    limit_per_req: int,
) -> list[uuid.UUID]:
    """Apps ranked by sum over requirements of weight * best capability or interface similarity among the hits.

    An interface hit counts for the catalog app at the matching end."""
    best: dict[uuid.UUID, dict[int, float]] = defaultdict(dict)

    def credit(app_id: uuid.UUID, i: int, sim: float) -> None:
        if sim > best[app_id].get(i, -1.0):
            best[app_id][i] = sim

    for i, vec in enumerate(req_vecs):
        dist = AppCapability.embedding.cosine_distance(vec).label("dist")
        rows = db.execute(
            select(AppCapability.app_id, dist)
            .join(App, App.id == AppCapability.app_id)
            .where(*conds, AppCapability.embedding.is_not(None), AppCapability.embedding_model == model_id)
            .order_by(dist)
            .limit(limit_per_req)
        ).all()
        for row in rows:
            credit(row.app_id, i, 1.0 - float(row.dist))
        for app_id, sim in _interface_hits(db, vec, conds, model_id, limit_per_req):
            credit(app_id, i, sim)
    scored = {app_id: sum(weights[i] * s for i, s in per_req.items()) for app_id, per_req in best.items()}
    return sorted(scored, key=lambda a: -scored[a])


def or_tsquery(db: Session, query_text: str) -> str | None:
    """German and English plainto_tsquery with AND turned into OR, so long inputs still match."""
    row = db.execute(
        text("SELECT plainto_tsquery('german', :q)::text AS de, plainto_tsquery('english', :q)::text AS en"),
        {"q": query_text},
    ).one()
    parts = [p.replace(" & ", " | ") for p in (row.de, row.en) if p]
    return " | ".join(f"({p})" for p in parts) if parts else None


def fts_ranking(db: Session, query_text: str, conds: list[ColumnElement[bool]], limit: int) -> list[uuid.UUID]:
    tsq_text = or_tsquery(db, query_text)
    if tsq_text is None:
        return []
    tsq = cast(literal(tsq_text), TSQUERY)
    rank = func.ts_rank_cd(App.search_tsv, tsq, _TS_RANK_SCALE_TO_UNIT).label("rank")
    rows = db.execute(
        select(App.id, rank).where(*conds, App.search_tsv.op("@@")(tsq)).order_by(rank.desc()).limit(limit)
    ).all()
    return [r.id for r in rows]


def _interface_caps(db: Session, app_ids: list[uuid.UUID], model_id: str) -> list[tuple[uuid.UUID, CandCap, Any]]:
    """Interfaces touching the candidates, each seen from the candidate's side."""
    wanted = set(app_ids)
    ifaces = db.scalars(
        select(Interface)
        .options(undefer(Interface.from_embedding), undefer(Interface.to_embedding))
        .where(
            or_(Interface.from_app_id.in_(app_ids), Interface.to_app_id.in_(app_ids)),
            Interface.embedded_at.is_not(None),
            Interface.embedding_model == model_id,
            Interface.status != InterfaceStatus.deprecated,
        )
        .order_by(Interface.name)
    ).unique()
    out: list[tuple[uuid.UUID, CandCap, Any]] = []
    for iface in ifaces:
        doc = interface_document(iface)
        for app_id, vec in ((iface.from_app_id, iface.from_embedding), (iface.to_app_id, iface.to_embedding)):
            if app_id not in wanted or vec is None:
                continue
            cap = CandCap(
                iface.id,
                "interface",
                doc,
                stem_map(doc),
                interface=to_summary(iface, app_id),
                capped=iface.status == InterfaceStatus.planned,
            )
            out.append((app_id, cap, vec))
    return out


def load_candidates(
    db: Session,
    app_ids: list[uuid.UUID],
    model_id: str,
    rrf: dict[uuid.UUID, float],
    ranks: dict[uuid.UUID, dict[str, int | None]],
) -> list[Candidate]:
    if not app_ids:
        return []
    summaries = {
        r.id: (
            np.asarray(r.summary_embedding, dtype=np.float32)
            if r.summary_embedding is not None and r.embedding_model == model_id
            else None
        )
        for r in db.execute(select(App.id, App.summary_embedding, App.embedding_model).where(App.id.in_(app_ids))).all()
    }
    caps: dict[uuid.UUID, list[tuple[CandCap, Any]]] = defaultdict(list)
    for r in db.execute(
        select(AppCapability.id, AppCapability.app_id, AppCapability.kind, AppCapability.text, AppCapability.embedding)
        .where(
            AppCapability.app_id.in_(app_ids),
            AppCapability.embedding.is_not(None),
            AppCapability.embedding_model == model_id,
        )
        .order_by(AppCapability.app_id, AppCapability.position)
    ).all():
        caps[r.app_id].append((CandCap(r.id, r.kind.value, r.text, stem_map(r.text)), r.embedding))
    for app_id, cap, vec in _interface_caps(db, app_ids, model_id):
        caps[app_id].append((cap, vec))

    out: list[Candidate] = []
    for app_id in app_ids:
        if app_id not in summaries:
            continue
        items = caps.get(app_id, [])
        matrix = np.stack([np.asarray(v, dtype=np.float32) for _, v in items]) if items else None
        out.append(
            Candidate(
                app_id, summaries[app_id], [c for c, _ in items], matrix, rrf.get(app_id, 0.0), ranks.get(app_id, {})
            )
        )
    return out


def similar_apps(db: Session, app_id: uuid.UUID, model_id: str, limit: int) -> list[tuple[App, float]]:
    source = db.scalar(select(App.summary_embedding).where(App.id == app_id, App.embedding_model == model_id))
    if source is None:
        return []
    dist = App.summary_embedding.cosine_distance(source).label("dist")
    rows = db.execute(
        select(App, dist)
        .where(
            App.id != app_id,
            App.summary_embedding.is_not(None),
            App.embedding_model == model_id,
            App.lifecycle_status != LifecycleStatus.retired,
        )
        .order_by(dist)
        .limit(limit)
    ).all()
    return [(row[0], 1.0 - float(row.dist)) for row in rows]

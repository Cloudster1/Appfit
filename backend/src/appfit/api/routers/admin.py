from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from appfit.api.deps import active_model_id
from appfit.auth.deps import require_admin
from appfit.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from appfit.db.engine import get_db
from appfit.models import ImportRun, SearchLog, User
from appfit.schemas.admin import EmbeddingStatusOut, ImportRunOut, ReindexRequest, SearchLogOut
from appfit.schemas.common import Page
from appfit.services.apps import EMBED_CHANNEL
from appfit.services.embedding_sync import embedding_counts, mark_all_stale

router = APIRouter(prefix="/admin", tags=["admin"])


def _status(request: Request, db: Session, model_id: str) -> EmbeddingStatusOut:
    counts = embedding_counts(db, model_id)
    worker = request.app.state.worker
    thread = request.app.state.worker_thread
    return EmbeddingStatusOut(
        model_id=model_id,
        model_loaded=request.app.state.embedder is not None,
        model_error=request.app.state.embedder_error,
        worker_running=bool(thread and thread.is_alive()),
        worker_last_error=worker.last_error if worker else None,
        apps_total=counts.apps_total,
        apps_indexed=counts.apps_indexed,
        capabilities_total=counts.capabilities_total,
        capabilities_indexed=counts.capabilities_indexed,
        interfaces_total=counts.interfaces_total,
        interfaces_indexed=counts.interfaces_indexed,
        pending=counts.pending,
    )


@router.get("/embeddings/status", response_model=EmbeddingStatusOut)
def embeddings_status(
    request: Request,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_admin),
) -> EmbeddingStatusOut:
    return _status(request, db, model_id)


@router.post("/embeddings/reindex", response_model=EmbeddingStatusOut)
def reindex(
    body: ReindexRequest,
    request: Request,
    db: Session = Depends(get_db),
    model_id: str = Depends(active_model_id),
    _: User = Depends(require_admin),
) -> EmbeddingStatusOut:
    if body.scope == "all":
        mark_all_stale(db)
    db.execute(text("SELECT pg_notify(:ch, '')"), {"ch": EMBED_CHANNEL})
    db.commit()
    return _status(request, db, model_id)


@router.get("/search-logs", response_model=Page[SearchLogOut])
def search_logs(
    only_feedback: bool = False,
    only_no_match: bool = False,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Page[SearchLogOut]:
    stmt = select(SearchLog)
    if only_feedback:
        stmt = stmt.where(SearchLog.feedback.is_not(None))
    if only_no_match:
        stmt = stmt.where(SearchLog.no_match.is_(True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(SearchLog.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return Page(items=[SearchLogOut.model_validate(r) for r in rows], total=total, page=page, size=size)


@router.get("/import-runs", response_model=list[ImportRunOut])
def import_runs(
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ImportRun]:
    return list(db.scalars(select(ImportRun).order_by(ImportRun.created_at.desc()).limit(limit)).all())

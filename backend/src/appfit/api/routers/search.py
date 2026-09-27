import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from appfit.api.deps import get_embedder
from appfit.auth.deps import require_viewer
from appfit.db.engine import get_db
from appfit.ml.embedder import Embedder
from appfit.models import SearchLog, User
from appfit.schemas.search import FeedbackIn, ParseRequest, ParseResponse, SearchRequest, SearchResponse
from appfit.services.errors import NotFoundError
from appfit.services.search.pipeline import parse_requirements, run_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/parse", response_model=ParseResponse)
def parse(body: ParseRequest, _: User = Depends(require_viewer)) -> ParseResponse:
    return ParseResponse(requirements=parse_requirements(body.text))


@router.post("", response_model=SearchResponse)
def search(
    body: SearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    user: User = Depends(require_viewer),
) -> SearchResponse:
    result = run_search(db, embedder, request.app.state.settings, body, user.id)
    db.commit()
    return result


@router.post("/{log_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(
    log_id: uuid.UUID,
    body: FeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
) -> None:
    log = db.get(SearchLog, log_id)
    if log is None:
        raise NotFoundError("Search not found")
    log.feedback = {**body.model_dump(), "user_id": str(user.id)}
    db.commit()

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from appfit.db.engine import get_db
from appfit.schemas.admin import HealthOut

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthOut)
def liveness() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/ready", response_model=HealthOut)
def readiness(request: Request, response: Response, db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    loaded = request.app.state.embedder is not None
    error = request.app.state.embedder_error
    if db_ok and loaded:
        return HealthOut(status="ok", database=True, model_loaded=True)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(
        status="error" if (error or not db_ok) else "starting",
        database=db_ok,
        model_loaded=loaded,
        detail=error or (None if db_ok else "database unreachable"),
    )

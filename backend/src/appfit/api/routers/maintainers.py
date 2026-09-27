import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from appfit.api.openapi import errors
from appfit.auth.deps import require_editor, require_viewer
from appfit.db.engine import get_db
from appfit.models import Maintainer, User
from appfit.schemas.app import MaintainerIn, MaintainerOut
from appfit.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/maintainers", tags=["maintainers"])


def _email_taken(db: Session, email: str | None, exclude: uuid.UUID | None = None) -> bool:
    if not email:
        return False
    stmt = select(Maintainer.id).where(Maintainer.email == email)
    if exclude is not None:
        stmt = stmt.where(Maintainer.id != exclude)
    return db.scalar(stmt) is not None


@router.get("", response_model=list[MaintainerOut])
def list_maintainers(
    q: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_viewer)
) -> list[Maintainer]:
    """People and teams, optionally filtered by name or email."""
    stmt = select(Maintainer).order_by(func.lower(Maintainer.name))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Maintainer.name.ilike(like), Maintainer.email.ilike(like)))
    return list(db.scalars(stmt).all())


@router.post(
    "", response_model=MaintainerOut, status_code=status.HTTP_201_CREATED, responses=errors(HTTPStatus.CONFLICT)
)
def create_maintainer(
    body: MaintainerIn, db: Session = Depends(get_db), _: User = Depends(require_editor)
) -> Maintainer:
    """Create a person or team."""
    if _email_taken(db, body.email):
        raise ConflictError("A maintainer with this email already exists")
    m = Maintainer(id=uuid.uuid4(), **body.model_dump())
    db.add(m)
    db.commit()
    return m


@router.patch("/{maintainer_id}", response_model=MaintainerOut, responses=errors(HTTPStatus.CONFLICT))
def update_maintainer(
    maintainer_id: uuid.UUID,
    body: MaintainerIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
) -> Maintainer:
    """Change a person or team."""
    m = db.get(Maintainer, maintainer_id)
    if m is None:
        raise NotFoundError("Maintainer not found")
    if _email_taken(db, body.email, exclude=m.id):
        raise ConflictError("A maintainer with this email already exists")
    for key, value in body.model_dump().items():
        setattr(m, key, value)
    db.commit()
    return m


@router.delete("/{maintainer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maintainer(
    maintainer_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_editor)
) -> None:
    """Delete a person or team and their app assignments."""
    m = db.get(Maintainer, maintainer_id)
    if m is None:
        raise NotFoundError("Maintainer not found")
    db.delete(m)
    db.commit()

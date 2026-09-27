import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appfit.api.openapi import errors
from appfit.auth.deps import require_admin
from appfit.auth.security import hash_password
from appfit.db.engine import get_db
from appfit.models import Role, User
from appfit.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    """All user accounts."""
    return list(db.scalars(select(User).order_by(func.lower(User.email))).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, responses=errors(HTTPStatus.CONFLICT))
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> User:
    """Create a local account with a role."""
    if db.scalar(select(User.id).where(func.lower(User.email) == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Change name, role, active flag or password; admins cannot demote or deactivate themselves."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and (body.is_active is False or (body.role and body.role != Role.admin)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot demote or deactivate yourself")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user

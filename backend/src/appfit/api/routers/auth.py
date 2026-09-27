from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from appfit.api.openapi import errors
from appfit.auth.deps import get_current_user, get_settings_dep
from appfit.auth.providers import LocalPasswordProvider
from appfit.auth.security import (
    clear_session_cookie,
    create_access_token,
    hash_password,
    set_session_cookie,
    verify_password,
)
from appfit.config import Settings
from appfit.db.engine import get_db
from appfit.models import User
from appfit.schemas.user import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
_provider = LocalPasswordProvider()


@router.post("/login", response_model=LoginResponse, responses=errors(HTTPStatus.UNAUTHORIZED))
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> LoginResponse:
    """Sign in with email and password; sets the session cookie and returns the token for bearer use."""
    user = _provider.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    db.commit()
    token = create_access_token(user.id, user.role.value, settings)
    set_session_cookie(response, token, settings)
    return LoginResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings_dep)) -> None:
    """Clear the session cookie."""
    clear_session_cookie(response, settings)


@router.get("/me", response_model=UserOut)
def current_user(user: User = Depends(get_current_user)) -> User:
    """The signed-in user."""
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Change the signed-in user's password; the current one must be given."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    db.commit()

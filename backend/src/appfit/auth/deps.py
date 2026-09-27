import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from appfit.auth.security import decode_access_token
from appfit.config import Settings
from appfit.db.engine import get_db
from appfit.models import Role, User

BEARER_PREFIX = "bearer "


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _token_from_request(request: Request, settings: Settings) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith(BEARER_PREFIX):
        return auth[len(BEARER_PREFIX) :].strip()
    return request.cookies.get(settings.cookie_name)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    token = _token_from_request(request, settings)
    if not token:
        raise unauthorized
    payload = decode_access_token(token, settings)
    if payload is None:
        raise unauthorized
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(min_role: Role) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.rank < min_role.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role {min_role.value}")
        return user

    return dependency


require_viewer = require_role(Role.viewer)
require_editor = require_role(Role.editor)
require_admin = require_role(Role.admin)

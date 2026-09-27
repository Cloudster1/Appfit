from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appfit.auth.security import verify_password
from appfit.models import User


class AuthProvider(Protocol):
    """Resolves credentials to an active user; an OIDC provider would implement the same seam."""

    name: str

    def authenticate(self, db: Session, username: str, secret: str) -> User | None: ...


class LocalPasswordProvider:
    name = "local"

    def authenticate(self, db: Session, username: str, secret: str) -> User | None:
        user = db.scalar(select(User).where(func.lower(User.email) == username.strip().lower()))
        if user is None or not user.is_active or user.auth_provider != self.name:
            return None
        if not verify_password(secret, user.password_hash):
            return None
        user.last_login_at = datetime.now(UTC)
        return user

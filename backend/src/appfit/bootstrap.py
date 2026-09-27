import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from appfit.auth.security import hash_password
from appfit.config import Settings
from appfit.models import Role, User

log = logging.getLogger(__name__)


def create_user(db: Session, email: str, password: str, display_name: str, role: Role) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email.strip().lower(),
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user


def bootstrap_admin(session_factory: sessionmaker[Session], settings: Settings) -> None:
    """Create the first admin from BOOTSTRAP_ADMIN_* when the users table is empty."""
    if not (settings.bootstrap_admin_email and settings.bootstrap_admin_password):
        return
    try:
        with session_factory() as db:
            if (db.scalar(select(func.count()).select_from(User)) or 0) > 0:
                return
            create_user(
                db, settings.bootstrap_admin_email, settings.bootstrap_admin_password, "Administrator", Role.admin
            )
            db.commit()
            log.warning("Bootstrap admin %s created; change its password.", settings.bootstrap_admin_email)
    except Exception:
        log.exception("Bootstrap admin creation failed (are migrations applied?)")

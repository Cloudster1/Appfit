from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from appfit.config import EMAIL_MAX_LEN, IDENT_MAX_LEN, NAME_MAX_LEN, PROVIDER_MAX_LEN
from appfit.db.base import Base
from appfit.models.enums import Role
from appfit.models.types import created_ts, str_enum, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LEN), unique=True)
    display_name: Mapped[str] = mapped_column(String(NAME_MAX_LEN))
    password_hash: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    role: Mapped[Role] = mapped_column(str_enum(Role), default=Role.viewer)
    auth_provider: Mapped[str] = mapped_column(String(PROVIDER_MAX_LEN), default="local")
    external_subject: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[created_ts]
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from appfit.config import NAME_MAX_LEN, PASSWORD_MAX_LEN, PASSWORD_MIN_LEN
from appfit.models import Role
from appfit.schemas.common import ORMModel
from appfit.schemas.types import NOT_BLANK_PATTERN, Email

Password = Annotated[str, Field(min_length=PASSWORD_MIN_LEN, max_length=PASSWORD_MAX_LEN)]


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    auth_provider: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: Email
    display_name: str = Field(min_length=1, max_length=NAME_MAX_LEN, pattern=NOT_BLANK_PATTERN)
    role: Role = Role.viewer
    password: Password


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LEN, pattern=NOT_BLANK_PATTERN)
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Password

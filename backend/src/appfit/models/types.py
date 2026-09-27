import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import mapped_column

from appfit.config import ENUM_MAX_LEN


def str_enum(enum_cls: type[StrEnum]) -> Enum:
    """Store a StrEnum as varchar + CHECK constraint (no native PG enum, easier migrations)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=ENUM_MAX_LEN,
        values_callable=lambda cls: [m.value for m in cls],
        name=enum_cls.__name__.lower(),
        validate_strings=True,
    )


uuid_pk = Annotated[uuid.UUID, mapped_column(primary_key=True, default=uuid.uuid4)]
created_ts = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
updated_ts = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
]

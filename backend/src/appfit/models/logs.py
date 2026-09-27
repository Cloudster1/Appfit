import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from appfit.config import IDENT_MAX_LEN, PROVIDER_MAX_LEN
from appfit.db.base import Base
from appfit.models.types import created_ts, uuid_pk


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    query_text: Mapped[str] = mapped_column(Text)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    no_match: Mapped[bool] = mapped_column(default=False)
    embedding_model: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    duration_ms: Mapped[int] = mapped_column(default=0)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[created_ts]


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    filename: Mapped[str | None] = mapped_column(String(IDENT_MAX_LEN))
    format: Mapped[str] = mapped_column(String(PROVIDER_MAX_LEN))
    mode: Mapped[str] = mapped_column(String(PROVIDER_MAX_LEN))
    dry_run: Mapped[bool] = mapped_column(default=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[created_ts]

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from appfit.schemas.common import ORMModel


class EmbeddingStatusOut(BaseModel):
    model_id: str
    model_loaded: bool
    model_error: str | None
    worker_running: bool
    worker_last_error: str | None
    apps_total: int
    apps_indexed: int
    capabilities_total: int
    capabilities_indexed: int
    interfaces_total: int
    interfaces_indexed: int
    pending: int


class ReindexRequest(BaseModel):
    scope: Literal["stale", "all"] = "stale"


class SearchLogOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    query_text: str
    requirements: list[dict[str, Any]]
    filters: dict[str, Any]
    results: list[dict[str, Any]]
    no_match: bool
    embedding_model: str | None
    duration_ms: int
    feedback: dict[str, Any] | None
    created_at: datetime


class ImportRunOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    filename: str | None
    format: str
    mode: str
    dry_run: bool
    stats: dict[str, Any]
    errors: list[dict[str, Any]]
    created_at: datetime


class HealthOut(BaseModel):
    status: Literal["ok", "starting", "error"]
    database: bool = True
    model_loaded: bool = False
    detail: str | None = None

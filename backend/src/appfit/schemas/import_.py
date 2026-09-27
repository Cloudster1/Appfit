import uuid
from typing import Literal

from pydantic import BaseModel

from appfit.schemas.app import AppFields
from appfit.schemas.interface import ExternalSystemIn, InterfaceIn

RowKind = Literal["app", "system", "interface"]

ImportMode = Literal["upsert", "create_only"]
ImportAction = Literal["created", "updated", "unchanged", "skipped", "invalid"]


class ImportFile(BaseModel):
    """JSON import/export document; export produces exactly this shape so files round-trip.

    Interfaces are applied after the apps, so they may refer to apps defined in the same file."""

    version: Literal[1] = 1
    apps: list[AppFields]
    external_systems: list[ExternalSystemIn] = []
    interfaces: list[InterfaceIn] = []


class ImportIssue(BaseModel):
    row: int
    kind: RowKind = "app"
    field: str | None = None
    message: str
    slug: str | None = None


class ImportItem(BaseModel):
    row: int
    kind: RowKind = "app"
    slug: str
    action: ImportAction
    changed_fields: list[str] = []


class ImportStats(BaseModel):
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    invalid: int = 0


class ImportReport(BaseModel):
    import_run_id: uuid.UUID | None
    format: str
    mode: ImportMode
    dry_run: bool
    committed: bool
    stats: ImportStats
    items: list[ImportItem]
    errors: list[ImportIssue]
    warnings: list[ImportIssue]

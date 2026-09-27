from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from appfit.auth.deps import require_editor, require_viewer
from appfit.config import Settings
from appfit.db.engine import get_db
from appfit.models import User
from appfit.schemas.import_ import ImportFile, ImportMode, ImportReport
from appfit.services.errors import ServiceError
from appfit.services.export import csv_template, export_csv, export_interfaces_csv, export_json
from appfit.services.importer.interfaces import interfaces_csv_template
from appfit.services.importer.parse_csv import parse_csv
from appfit.services.importer.parse_json import parse_json
from appfit.services.importer.rows import ImportFormatError
from appfit.services.importer.upsert import run_import

router = APIRouter(tags=["import"])

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


def _detect_format(filename: str | None, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".json"):
        return "json"
    if name.endswith((".csv", ".txt", ".tsv")):
        return "csv"
    return "json" if content.lstrip()[:1] in (b"{", b"[") else "csv"


@router.post("/import", response_model=ImportReport)
async def import_file(
    request: Request,
    file: UploadFile = File(...),
    format: Literal["auto", "csv", "json"] = "auto",
    mode: ImportMode = "upsert",
    dry_run: bool = Query(default=True),
    skip_invalid: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
) -> ImportReport:
    settings: Settings = request.app.state.settings
    content = await file.read(settings.import_max_bytes + 1)
    if len(content) > settings.import_max_bytes:
        raise ServiceError(f"File exceeds {settings.import_max_bytes} bytes")
    fmt = _detect_format(file.filename, content) if format == "auto" else format
    try:
        rows, warnings = parse_json(content) if fmt == "json" else parse_csv(content)
    except ImportFormatError as exc:
        raise ServiceError(str(exc)) from None
    if len(rows) > settings.import_max_apps:
        raise ServiceError(f"Too many rows ({len(rows)}); the limit is {settings.import_max_apps}")
    report = run_import(
        db,
        rows,
        fmt=fmt,
        mode=mode,
        dry_run=dry_run,
        skip_invalid=skip_invalid,
        user_id=user.id,
        filename=file.filename,
        parse_warnings=warnings,
    )
    db.commit()
    return report


@router.get("/import/template.csv", response_class=PlainTextResponse)
def template(_: User = Depends(require_viewer)) -> Response:
    return Response(
        csv_template(),
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="appfit-template.csv"'},
    )


@router.get("/import/interfaces-template.csv", response_class=PlainTextResponse)
def interfaces_template(_: User = Depends(require_viewer)) -> Response:
    return Response(
        interfaces_csv_template(),
        media_type=CSV_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="appfit-interfaces-template.csv"'},
    )


@router.get("/import/schema.json")
def schema(_: User = Depends(require_viewer)) -> dict[str, Any]:
    return ImportFile.model_json_schema()


@router.get("/export", response_model=None)
def export(
    format: Literal["json", "csv"] = "json",
    kind: Literal["apps", "interfaces"] = Query(default="apps", description="CSV only: which table to export"),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
) -> Response | dict[str, Any]:
    if format == "csv" and kind == "interfaces":
        return Response(
            export_interfaces_csv(db),
            media_type=CSV_MEDIA_TYPE,
            headers={"Content-Disposition": 'attachment; filename="appfit-interfaces.csv"'},
        )
    if format == "csv":
        return Response(
            export_csv(db),
            media_type=CSV_MEDIA_TYPE,
            headers={"Content-Disposition": 'attachment; filename="appfit-export.csv"'},
        )
    return export_json(db)

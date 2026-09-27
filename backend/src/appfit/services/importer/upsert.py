import uuid
from collections.abc import Callable
from functools import partial
from typing import Any

from pydantic import ValidationError
from slugify import slugify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from appfit.config import SLUG_MAX_LEN
from appfit.models import ImportRun
from appfit.schemas.app import AppFields, CapabilityIn
from appfit.schemas.import_ import ImportIssue, ImportItem, ImportMode, ImportReport, ImportStats
from appfit.services.apps import create_app, get_app, update_app
from appfit.services.errors import ServiceError
from appfit.services.importer.aliases import normalize_aliases
from appfit.services.importer.interfaces import apply_interface, apply_system, validate_interfaces, validate_systems
from appfit.services.importer.rows import RawRow

REQUIRED_ON_UPDATE = ("name", "slug")


class _AbortImport(Exception):
    pass


def _validation_issues(row: RawRow, exc: ValidationError, slug: str | None) -> list[ImportIssue]:
    return [
        ImportIssue(
            row=row.number,
            field=".".join(str(p) for p in err["loc"]) or None,
            message=err["msg"],
            slug=slug,
        )
        for err in exc.errors()
    ]


def _merge_row_extras(app: Any, row: RawRow, data: dict[str, Any]) -> None:
    if row.keep_capability_kinds and app is not None and "capabilities" in data:
        kept = [
            CapabilityIn(id=c.id, kind=c.kind, text=c.text, details=c.details)
            for c in app.capabilities
            if c.kind.value in row.keep_capability_kinds
        ]
        data["capabilities"] = list(data["capabilities"]) + kept
    if row.extra_merge is not None:
        extra = dict(app.extra or {}) if app is not None else {}
        for key, value in row.extra_merge.items():
            if value is None:
                extra.pop(key, None)
            else:
                extra[key] = value
        data["extra"] = extra


def run_import(
    db: Session,
    rows: list[RawRow],
    *,
    fmt: str,
    mode: ImportMode,
    dry_run: bool,
    skip_invalid: bool,
    user_id: uuid.UUID | None,
    filename: str | None,
    parse_warnings: list[str] | None = None,
) -> ImportReport:
    """Validate all rows, then apply them in one savepoint; nothing is written on errors or dry runs.

    Apps go first, then external systems, then interfaces, so interfaces can refer to apps of the same file."""
    stats = ImportStats(total=len(rows))
    errors: list[ImportIssue] = []
    warnings = [ImportIssue(row=0, message=w) for w in parse_warnings or []]
    items: list[ImportItem] = []

    app_rows = [r for r in rows if r.kind == "app"]
    systems = validate_systems([r for r in rows if r.kind == "system"], errors)
    interfaces = validate_interfaces([r for r in rows if r.kind == "interface"], errors)
    stats.invalid += len(rows) - len(app_rows) - len(systems) - len(interfaces)

    validated: list[tuple[RawRow, str, AppFields]] = []
    seen: dict[str, int] = {}
    for row in app_rows:
        data = normalize_aliases(dict(row.data))
        for key in REQUIRED_ON_UPDATE:
            if key in data and data[key] in (None, ""):
                del data[key]
        guess = data.get("slug") or (slugify(str(data["name"]), max_length=SLUG_MAX_LEN) if data.get("name") else None)
        try:
            fields = AppFields.model_validate(data)
        except ValidationError as exc:
            errors.extend(_validation_issues(row, exc, guess))
            stats.invalid += 1
            continue
        slug = fields.slug or (slugify(fields.name, max_length=SLUG_MAX_LEN) if fields.name else None)
        if not slug:
            errors.append(ImportIssue(row=row.number, field="slug", message="slug or name is required"))
            stats.invalid += 1
            continue
        if slug in seen:
            errors.append(
                ImportIssue(
                    row=row.number, field="slug", slug=slug, message=f"duplicate slug, already used in row {seen[slug]}"
                )
            )
            stats.invalid += 1
            continue
        seen[slug] = row.number
        validated.append((row, slug, fields))

    abort = bool(errors) and not skip_invalid
    committed = False
    if not abort:
        savepoint = db.begin_nested()
        steps: list[tuple[RawRow, str, Callable[[], ImportItem]]] = [
            (row, slug, partial(_apply_row, db, row, slug, fields, mode, user_id, warnings, stats))
            for row, slug, fields in validated
        ]
        steps += [(v.row, v.label, partial(apply_system, db, v, mode, stats)) for v in systems]
        steps += [(v.row, v.label, partial(apply_interface, db, v, mode, user_id, stats)) for v in interfaces]
        try:
            for row, label, step in steps:
                try:
                    with db.begin_nested():
                        items.append(step())
                except (ServiceError, IntegrityError) as exc:
                    msg = exc.message if isinstance(exc, ServiceError) else str(exc.orig).splitlines()[0]
                    errors.append(ImportIssue(row=row.number, kind=row.kind, slug=label, message=msg))
                    stats.invalid += 1
                    items.append(ImportItem(row=row.number, kind=row.kind, slug=label, action="invalid"))
                    if not skip_invalid:
                        raise _AbortImport from exc
        except _AbortImport:
            abort = True
        if dry_run or abort:
            savepoint.rollback()
        else:
            savepoint.commit()
            committed = True

    run = ImportRun(
        id=uuid.uuid4(),
        user_id=user_id,
        filename=filename,
        format=fmt,
        mode=mode,
        dry_run=dry_run,
        stats=stats.model_dump(),
        errors=[e.model_dump() for e in errors],
    )
    db.add(run)
    db.flush()
    return ImportReport(
        import_run_id=run.id,
        format=fmt,
        mode=mode,
        dry_run=dry_run,
        committed=committed,
        stats=stats,
        items=items,
        errors=errors,
        warnings=warnings,
    )


def _apply_row(
    db: Session,
    row: RawRow,
    slug: str,
    fields: AppFields,
    mode: ImportMode,
    user_id: uuid.UUID | None,
    warnings: list[ImportIssue],
    stats: ImportStats,
) -> ImportItem:
    present = fields.model_fields_set - {"slug"}
    data: dict[str, Any] = {name: getattr(fields, name) for name in present}
    app = get_app(db, slug)
    _merge_row_extras(app, row, data)
    if app is None:
        if not fields.name:
            raise ServiceError("name is required to create a new app")
        _, result = create_app(db, {**data, "slug": slug}, user_id)
        stats.created += 1
        action, changed = "created", result.changed_fields
    elif mode == "create_only":
        stats.skipped += 1
        return ImportItem(row=row.number, slug=slug, action="skipped")
    else:
        result = update_app(db, app, data, user_id)
        changed = result.changed_fields
        if changed:
            stats.updated += 1
            action = "updated"
        else:
            stats.unchanged += 1
            action = "unchanged"
    warnings.extend(ImportIssue(row=row.number, slug=slug, message=w) for w in result.warnings)
    return ImportItem(row=row.number, slug=slug, action=action, changed_fields=changed)

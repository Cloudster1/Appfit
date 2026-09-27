"""Import and export of external systems and interfaces; applied after the apps of the same file."""

import csv
import io
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appfit.models import ExternalSystem, Interface
from appfit.schemas.import_ import ImportIssue, ImportItem, ImportMode, ImportStats
from appfit.schemas.interface import ExternalSystemIn, InterfaceIn
from appfit.services.importer.rows import RawRow, split_multi
from appfit.services.interfaces import (
    create_interface,
    find_interface,
    find_system,
    resolve_endpoint,
    update_interface,
)

INTERFACE_CSV_COLUMNS = (
    "from",
    "to",
    "name",
    "type",
    "data_objects",
    "frequency",
    "status",
    "bidirectional",
    "description",
)
SYSTEM_PREFIX, APP_PREFIX = "system:", "app:"
TRUE_WORDS = {"true", "yes", "ja", "1", "x", "wahr"}
FALSE_WORDS = {"false", "no", "nein", "0", "", "falsch"}

# An empty cell or null resets these to their default; frequency is nullable and simply cleared.
INTERFACE_DEFAULTS: dict[str, Any] = {
    "type": "other",
    "status": "active",
    "bidirectional": False,
    "description": "",
    "data_objects": [],
}
TYPE_ALIASES = {
    "rest": "rest_api",
    "rest-api": "rest_api",
    "rest api": "rest_api",
    "api": "rest_api",
    "http": "rest_api",
    "soap": "soap",
    "webservice": "soap",
    "datei": "file_transfer",
    "dateitransfer": "file_transfer",
    "file": "file_transfer",
    "sftp": "file_transfer",
    "csv": "file_transfer",
    "datenbank": "database",
    "db": "database",
    "events": "messaging",
    "event": "messaging",
    "nachrichten": "messaging",
    "queue": "messaging",
    "kafka": "messaging",
    "identity": "sso",
    "scim": "sso",
    "saml": "sso",
    "ui": "ui_embedding",
    "iframe": "ui_embedding",
    "sonstige": "other",
    "andere": "other",
}
STATUS_ALIASES = {
    "geplant": "planned",
    "planung": "planned",
    "aktiv": "active",
    "produktiv": "active",
    "live": "active",
    "veraltet": "deprecated",
    "abgekuendigt": "deprecated",
    "auslaufend": "deprecated",
}
FREQUENCY_ALIASES = {
    "echtzeit": "realtime",
    "real-time": "realtime",
    "real time": "realtime",
    "sofort": "realtime",
    "stapel": "batch",
    "nachtlauf": "batch",
    "taeglich": "batch",
    "daily": "batch",
    "nightly": "batch",
    "bei bedarf": "on_demand",
    "on demand": "on_demand",
    "manuell": "on_demand",
}


def _alias(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, str):
        key = value.strip().lower()
        return aliases.get(key, key)
    return value


def normalize_interface(data: dict[str, Any]) -> dict[str, Any]:
    """German aliases, defaults for empty values and "app:" / "system:" endpoint cells."""
    for key, default in INTERFACE_DEFAULTS.items():
        if key in data and data[key] is None:
            data[key] = default
    if "type" in data:
        data["type"] = _alias(data["type"], TYPE_ALIASES)
    if "status" in data:
        data["status"] = _alias(data["status"], STATUS_ALIASES)
    if data.get("frequency") is not None:
        data["frequency"] = _alias(data["frequency"], FREQUENCY_ALIASES)
    if isinstance(data.get("bidirectional"), str):
        word = data["bidirectional"].strip().lower()
        data["bidirectional"] = True if word in TRUE_WORDS else False if word in FALSE_WORDS else word
    for side in ("from", "to"):
        if isinstance(data.get(side), str):
            data[side] = endpoint_from_cell(data[side])
    return data


def endpoint_from_cell(cell: str) -> dict[str, str]:
    value = cell.strip()
    if value.lower().startswith(SYSTEM_PREFIX):
        return {"system": value[len(SYSTEM_PREFIX) :].strip()}
    if value.lower().startswith(APP_PREFIX):
        return {"app": value[len(APP_PREFIX) :].strip()}
    return {"app": value}


def endpoint_label(ref: dict[str, Any] | Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("app") or ref.get("system") or "?")
    return "?"


def interface_label(data: dict[str, Any]) -> str:
    return f"{endpoint_label(data.get('from'))} -> {endpoint_label(data.get('to'))}: {data.get('name') or '?'}"


def is_interface_csv(headers: list[str]) -> bool:
    return "from" in headers and "to" in headers


def parse_interface_rows(reader: csv.DictReader[str], headers: list[str]) -> tuple[list[RawRow], list[str]]:
    warnings = [f"Unknown column ignored: {h!r}" for h in headers if h and h not in INTERFACE_CSV_COLUMNS]
    rows: list[RawRow] = []
    for line_no, rec in enumerate(reader, start=2):
        cell = {k: (v or "").strip() for k, v in rec.items() if k and isinstance(v, str)}
        if not any(cell.values()):
            continue
        data: dict[str, Any] = {}
        for col in INTERFACE_CSV_COLUMNS:
            if col not in headers:
                continue
            if col == "data_objects":
                data[col] = split_multi(cell.get(col, ""))
            else:
                data[col] = cell.get(col) or None
        rows.append(RawRow(number=line_no, data=data, kind="interface"))
    return rows, warnings


# Export


def interface_to_import_dict(iface: Interface) -> dict[str, Any]:
    def ref(app_slug: str | None, system: ExternalSystem | None) -> dict[str, str]:
        return {"app": app_slug} if app_slug else {"system": system.name if system else ""}

    return {
        "from": ref(iface.from_app.slug if iface.from_app else None, iface.from_system),
        "to": ref(iface.to_app.slug if iface.to_app else None, iface.to_system),
        "name": iface.name,
        "type": iface.interface_type.value,
        "data_objects": list(iface.data_objects),
        "frequency": iface.frequency.value if iface.frequency else None,
        "status": iface.status.value,
        "bidirectional": iface.bidirectional,
        "description": iface.description,
    }


def system_to_import_dict(system: ExternalSystem) -> dict[str, Any]:
    return {"name": system.name, "description": system.description, "vendor": system.vendor, "url": system.url}


def all_interfaces(db: Session) -> list[Interface]:
    return list(db.scalars(select(Interface).order_by(func.lower(Interface.name), Interface.id)).unique().all())


def all_systems(db: Session) -> list[ExternalSystem]:
    return list(db.scalars(select(ExternalSystem).order_by(func.lower(ExternalSystem.name))).all())


def _cell(ref: dict[str, str]) -> str:
    return f"{APP_PREFIX}{ref['app']}" if "app" in ref else f"{SYSTEM_PREFIX}{ref['system']}"


def interfaces_csv(db: Session, join: Any) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(INTERFACE_CSV_COLUMNS)
    for d in (interface_to_import_dict(i) for i in all_interfaces(db)):
        writer.writerow(
            [
                _cell(d["from"]),
                _cell(d["to"]),
                d["name"],
                d["type"],
                join(d["data_objects"]),
                d["frequency"] or "",
                d["status"],
                "true" if d["bidirectional"] else "false",
                d["description"],
            ]
        )
    return buf.getvalue()


def interfaces_csv_template() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(INTERFACE_CSV_COLUMNS)
    writer.writerow(
        [
            "app:invoice-hub",
            "system:SAP S/4HANA",
            "Posting of approved invoices",
            "rest_api",
            "invoices|postings",
            "realtime",
            "active",
            "false",
            "Approved invoices are posted to SAP FI as vendor invoices.",
        ]
    )
    writer.writerow(
        [
            "app:hr-portal",
            "app:invoice-hub",
            "Cost centres",
            "file_transfer",
            "cost centres",
            "batch",
            "planned",
            "",
            "",
        ]
    )
    return buf.getvalue()


# Validation and apply


@dataclass
class ValidRow:
    row: RawRow
    label: str
    present: dict[str, Any]


def _issues(row: RawRow, exc: ValidationError, label: str) -> list[ImportIssue]:
    return [
        ImportIssue(
            row=row.number,
            kind=row.kind,
            field=".".join(str(p) for p in err["loc"]) or None,
            message=err["msg"],
            slug=label,
        )
        for err in exc.errors()
    ]


def validate_systems(rows: list[RawRow], errors: list[ImportIssue]) -> list[ValidRow]:
    valid: list[ValidRow] = []
    seen: dict[str, int] = {}
    for row in rows:
        label = str(row.data.get("name") or "?")
        try:
            ExternalSystemIn.model_validate(row.data)
        except ValidationError as exc:
            errors.extend(_issues(row, exc, label))
            continue
        key = label.strip().lower()
        if key in seen:
            errors.append(
                ImportIssue(row=row.number, kind="system", slug=label, message=f"duplicate, see row {seen[key]}")
            )
            continue
        seen[key] = row.number
        valid.append(ValidRow(row, label, dict(row.data)))
    return valid


def validate_interfaces(rows: list[RawRow], errors: list[ImportIssue]) -> list[ValidRow]:
    valid: list[ValidRow] = []
    seen: dict[tuple[str, str, str], int] = {}
    for row in rows:
        data = normalize_interface(dict(row.data))
        label = interface_label(data)
        try:
            fields = InterfaceIn.model_validate(data)
        except ValidationError as exc:
            errors.extend(_issues(row, exc, label))
            continue
        key = (
            endpoint_label(fields.source.model_dump()).lower(),
            endpoint_label(fields.target.model_dump()).lower(),
            fields.name.lower(),
        )
        if key in seen:
            errors.append(
                ImportIssue(row=row.number, kind="interface", slug=label, message=f"duplicate, see row {seen[key]}")
            )
            continue
        seen[key] = row.number
        valid.append(ValidRow(row, label, data))
    return valid


def apply_system(db: Session, v: ValidRow, mode: ImportMode, stats: ImportStats) -> ImportItem:
    fields = ExternalSystemIn.model_validate(v.present)
    system = find_system(db, fields.name)
    if system is None:
        db.add(
            ExternalSystem(
                id=uuid.uuid4(), name=fields.name, description=fields.description, vendor=fields.vendor, url=fields.url
            )
        )
        db.flush()
        stats.created += 1
        return ImportItem(row=v.row.number, kind="system", slug=v.label, action="created")
    if mode == "create_only":
        stats.skipped += 1
        return ImportItem(row=v.row.number, kind="system", slug=v.label, action="skipped")
    changed = [
        f for f in ("description", "vendor", "url") if f in v.present and getattr(system, f) != getattr(fields, f)
    ]
    for f in changed:
        setattr(system, f, getattr(fields, f))
    db.flush()
    action = "updated" if changed else "unchanged"
    setattr(stats, action, getattr(stats, action) + 1)
    return ImportItem(row=v.row.number, kind="system", slug=v.label, action=action, changed_fields=changed)


def apply_interface(
    db: Session, v: ValidRow, mode: ImportMode, user_id: uuid.UUID | None, stats: ImportStats
) -> ImportItem:
    fields = InterfaceIn.model_validate(v.present)
    source, target = resolve_endpoint(db, fields.source), resolve_endpoint(db, fields.target)
    existing = find_interface(db, source, target, fields.name)
    if existing is None:
        create_interface(db, fields, user_id)
        stats.created += 1
        return ImportItem(row=v.row.number, kind="interface", slug=v.label, action="created")
    if mode == "create_only":
        stats.skipped += 1
        return ImportItem(row=v.row.number, kind="interface", slug=v.label, action="skipped")
    # A missing key keeps the stored value, like for apps.
    merged = InterfaceIn.model_validate({**interface_to_import_dict(existing), **v.present})
    before = interface_to_import_dict(existing)
    changed = update_interface(db, existing, merged, user_id)
    after = interface_to_import_dict(existing)
    fields_changed = [k for k in after if after[k] != before[k]]
    action = "updated" if changed else "unchanged"
    setattr(stats, action, getattr(stats, action) + 1)
    return ImportItem(row=v.row.number, kind="interface", slug=v.label, action=action, changed_fields=fields_changed)

import csv
import io
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appfit.config import CSV_MULTI_VALUE_SEPARATOR, IMPORT_FORMAT_VERSION
from appfit.models import App, CapabilityKind, TagCategory
from appfit.services.importer.interfaces import (
    all_interfaces,
    all_systems,
    interface_to_import_dict,
    interfaces_csv,
    system_to_import_dict,
)
from appfit.services.importer.parse_csv import (
    CAPABILITY_COLUMNS,
    CSV_COLUMNS,
    EXTRA_PREFIX,
    LIST_COLUMNS,
    SCALAR_COLUMNS,
)
from appfit.services.importer.rows import csv_safe

_TAG_FIELD = {TagCategory.general: "tags", TagCategory.tech: "tech_stack", TagCategory.domain: "domains"}


def app_to_import_dict(app: App) -> dict[str, Any]:
    tags: dict[str, list[str]] = {"tags": [], "tech_stack": [], "domains": []}
    for t in app.tags:
        tags[_TAG_FIELD[t.category]].append(t.name)
    return {
        "slug": app.slug,
        "name": app.name,
        "short_description": app.short_description,
        "description": app.description,
        "lifecycle_status": app.lifecycle_status.value,
        "license": app.license,
        "license_type": app.license_type.value if app.license_type else None,
        "vendor": app.vendor,
        "version": app.version,
        "homepage_url": app.homepage_url,
        "repo_url": app.repo_url,
        "docs_url": app.docs_url,
        "links": app.links or [],
        "extra": app.extra or {},
        **tags,
        "maintainers": [
            {
                "name": link.maintainer.name,
                "email": link.maintainer.email,
                "kind": link.maintainer.kind.value,
                "org_unit": link.maintainer.org_unit,
                "role": link.role.value,
            }
            for link in app.maintainer_links
        ],
        "capabilities": [{"kind": c.kind.value, "text": c.text, "details": c.details} for c in app.capabilities],
    }


def _all_apps(db: Session) -> list[App]:
    return list(db.scalars(select(App).order_by(func.lower(App.name))).all())


def export_json(db: Session) -> dict[str, Any]:
    return {
        "version": IMPORT_FORMAT_VERSION,
        "apps": [app_to_import_dict(a) for a in _all_apps(db)],
        "external_systems": [system_to_import_dict(s) for s in all_systems(db)],
        "interfaces": [interface_to_import_dict(i) for i in all_interfaces(db)],
    }


def _join(values: list[str]) -> str:
    return CSV_MULTI_VALUE_SEPARATOR.join(v.replace(CSV_MULTI_VALUE_SEPARATOR, "/") for v in values)


def _maintainer_cell(m: dict[str, Any]) -> str:
    email = f" <{m['email']}>" if m.get("email") else ""
    return f"{m['role']}:{m['name']}{email}"


def export_interfaces_csv(db: Session) -> str:
    return interfaces_csv(db, _join)


def export_csv(db: Session) -> str:
    dicts = [app_to_import_dict(a) for a in _all_apps(db)]
    extra_keys = sorted({k for d in dicts for k in d["extra"]})
    header = [*CSV_COLUMNS, *(EXTRA_PREFIX + k for k in extra_keys)]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    kind_to_col = {v: k for k, v in CAPABILITY_COLUMNS.items()}
    for d in dicts:
        row: dict[str, str] = {c: "" if d.get(c) is None else str(d[c]) for c in SCALAR_COLUMNS}
        for c in LIST_COLUMNS:
            row[c] = _join(d[c])
        row["maintainers"] = _join([_maintainer_cell(m) for m in d["maintainers"]])
        for kind in CapabilityKind:
            row[kind_to_col[kind.value]] = _join([c["text"] for c in d["capabilities"] if c["kind"] == kind.value])
        row["links"] = _join([f"{link['label']}={link['url']}" for link in d["links"]])
        for k in extra_keys:
            v = d["extra"].get(k)
            row[EXTRA_PREFIX + k] = "" if v is None else str(v)
        writer.writerow([csv_safe(row.get(c, "")) for c in header])
    return buf.getvalue()


def csv_template() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    example = {
        "slug": "invoice-hub",
        "name": "Invoice Hub",
        "short_description": "Central processing of incoming supplier invoices",
        "description": "Captures PDF and XRechnung invoices, extracts data and routes them for approval.",
        "lifecycle_status": "active",
        "license": "Proprietary",
        "license_type": "commercial",
        "vendor": "ACME GmbH",
        "version": "4.2",
        "homepage_url": "https://invoice-hub.example.com",
        "repo_url": "",
        "docs_url": "https://docs.example.com/invoice-hub",
        "tags": "finance|invoices",
        "tech_stack": "java|postgresql",
        "domains": "accounting",
        "maintainers": "owner:Jane Doe <jane.doe@example.com>|contact:Team Finance IT",
        "capabilities": "OCR extraction of invoice data|Multi-level approval workflow",
        "requirements": "Runs on-premises",
        "features": "Export to SAP FI",
        "links": "Wiki=https://wiki.example.com/invoice-hub",
    }
    writer.writerow([example.get(c, "") for c in CSV_COLUMNS])
    return buf.getvalue()

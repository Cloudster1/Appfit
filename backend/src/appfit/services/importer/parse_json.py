import json
from typing import Any

from appfit.config import IMPORT_FORMAT_VERSION
from appfit.schemas.import_ import RowKind
from appfit.services.importer.parse_csv import decode
from appfit.services.importer.rows import ImportFormatError, RawRow


def _section(doc: dict[str, Any], key: str, kind: RowKind) -> list[RawRow]:
    items = doc.get(key) or []
    if not isinstance(items, list):
        raise ImportFormatError(f"'{key}' must be a list")
    rows = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ImportFormatError(f"{key} #{i} is not an object")
        rows.append(RawRow(number=i, data=dict(item), kind=kind))
    return rows


def parse_json(content: bytes) -> tuple[list[RawRow], list[str]]:
    """Accepts {"version": 1, "apps": [...], "external_systems": [...], "interfaces": [...]} or a bare app list.

    A missing key keeps a field, null clears it."""
    try:
        doc: Any = json.loads(decode(content))
    except json.JSONDecodeError as exc:
        raise ImportFormatError(f"Invalid JSON: {exc.msg} (line {exc.lineno})") from None
    if isinstance(doc, dict):
        version = doc.get("version", IMPORT_FORMAT_VERSION)
        if version != IMPORT_FORMAT_VERSION:
            raise ImportFormatError(f"Unsupported format version {version!r}")
        apps = doc.get("apps", [])
        extra_rows = _section(doc, "external_systems", "system") + _section(doc, "interfaces", "interface")
    else:
        apps, extra_rows = doc, []
    if not isinstance(apps, list):
        raise ImportFormatError("Expected a list of apps (or an object with an 'apps' list)")
    rows: list[RawRow] = []
    warnings: list[str] = []
    for i, item in enumerate(apps, start=1):
        if not isinstance(item, dict):
            raise ImportFormatError(f"App #{i} is not an object")
        rows.append(RawRow(number=i, data=dict(item)))
    return rows + extra_rows, warnings

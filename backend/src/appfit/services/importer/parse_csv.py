import csv
import io
import re
from typing import Any

from appfit.config import CSV_SNIFF_BYTES
from appfit.models import CapabilityKind
from appfit.services.importer.interfaces import is_interface_csv, parse_interface_rows
from appfit.services.importer.rows import ImportFormatError, RawRow, split_multi

SCALAR_COLUMNS = (
    "slug",
    "name",
    "short_description",
    "description",
    "lifecycle_status",
    "license",
    "license_type",
    "vendor",
    "version",
    "homepage_url",
    "repo_url",
    "docs_url",
)
LIST_COLUMNS = ("tags", "tech_stack", "domains")
CAPABILITY_COLUMNS = {"capabilities": "capability", "requirements": "requirement", "features": "feature"}
CSV_COLUMNS = (*SCALAR_COLUMNS, *LIST_COLUMNS, "maintainers", *CAPABILITY_COLUMNS, "links")
EXTRA_PREFIX = "extra."

_MAINTAINER_RE = re.compile(r"^(?:(?P<role>[^:<]+):)?\s*(?P<name>[^<]*?)\s*(?:<(?P<email>[^>]+)>)?\s*$")
_TEAM_PREFIXES = ("team ", "team-")


def decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFormatError("File is neither UTF-8 nor Windows-1252 encoded")


def parse_maintainer(cell: str) -> dict[str, Any]:
    m = _MAINTAINER_RE.match(cell.strip())
    if not m:
        return {"name": cell.strip()}
    out: dict[str, Any] = {}
    name = (m.group("name") or "").strip()
    if name:
        out["name"] = name
        out["kind"] = "team" if name.lower().startswith(_TEAM_PREFIXES) else "person"
    if m.group("email"):
        out["email"] = m.group("email").strip()
    if m.group("role"):
        out["role"] = m.group("role").strip()
    return out


def parse_link(cell: str) -> dict[str, str]:
    label, sep, url = cell.partition("=")
    if not sep:
        url = cell.strip()
        label = re.sub(r"^https?://(www\.)?", "", url).split("/")[0] or url
    return {"label": label.strip(), "url": url.strip()}


def _sniff_dialect(text: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(text[:CSV_SNIFF_BYTES], delimiters=",;\t")
    except csv.Error:
        return csv.excel


def parse_csv(content: bytes) -> tuple[list[RawRow], list[str]]:
    """One app per row, or one interface per row when the header has "from" and "to" columns.

    A missing column leaves a field untouched, an empty cell clears it."""
    text = decode(content)
    if not text.strip():
        raise ImportFormatError("File is empty")
    reader = csv.DictReader(io.StringIO(text), dialect=_sniff_dialect(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    if is_interface_csv(headers):
        return parse_interface_rows(reader, headers)
    if "name" not in headers and "slug" not in headers:
        raise ImportFormatError("CSV needs at least a 'name' or 'slug' column")
    reader.fieldnames = headers
    warnings = [
        f"Unknown column ignored: {h!r}"
        for h in headers
        if h and h not in CSV_COLUMNS and not h.startswith(EXTRA_PREFIX)
    ]
    present_cap_cols = [c for c in CAPABILITY_COLUMNS if c in headers]
    extra_cols = [h for h in headers if h.startswith(EXTRA_PREFIX) and len(h) > len(EXTRA_PREFIX)]

    rows: list[RawRow] = []
    for line_no, rec in enumerate(reader, start=2):
        if not any((v or "").strip() for v in rec.values() if isinstance(v, str)):
            continue
        cell = {k: (v or "").strip() if isinstance(v, str) else "" for k, v in rec.items() if k}
        data: dict[str, Any] = {}
        for col in SCALAR_COLUMNS:
            if col in headers:
                data[col] = cell[col] or None
        for col in LIST_COLUMNS:
            if col in headers:
                data[col] = split_multi(cell[col])
        if "maintainers" in headers:
            data["maintainers"] = [parse_maintainer(v) for v in split_multi(cell["maintainers"])]
        if "links" in headers:
            data["links"] = [parse_link(v) for v in split_multi(cell["links"])]
        if present_cap_cols:
            data["capabilities"] = [
                {"kind": CAPABILITY_COLUMNS[col], "text": text_}
                for col in present_cap_cols
                for text_ in split_multi(cell[col])
            ]
        row = RawRow(number=line_no, data=data)
        if present_cap_cols:
            row.keep_capability_kinds = [
                k.value for k in CapabilityKind if k.value not in {CAPABILITY_COLUMNS[c] for c in present_cap_cols}
            ]
        if extra_cols:
            row.extra_merge = {c[len(EXTRA_PREFIX) :]: (cell[c] or None) for c in extra_cols}
        rows.append(row)
    return rows, warnings

import csv
import io
import re
from typing import Any

from appfit.config import CSV_SNIFF_BYTES
from appfit.models import CapabilityKind
from appfit.services.importer.interfaces import is_interface_csv, parse_interface_rows
from appfit.services.importer.rows import ImportFormatError, RawRow, csv_unescape, numbered_records, split_multi
from appfit.text import NUL

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
_URL_START_RE = re.compile(r"^https?://", re.IGNORECASE)
_LABELLED_LINK_RE = re.compile(r"^(?P<label>.*?)=(?P<url>https?://.*)$", re.IGNORECASE)


def decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        if NUL in text:
            raise ImportFormatError("File contains NUL characters; is it a text file?")
        return text
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
    """Either "Label=URL" or a bare URL; URLs and labels may themselves contain "="."""
    cell = cell.strip()
    if not _URL_START_RE.match(cell):
        labelled = _LABELLED_LINK_RE.match(cell)
        label, sep, url = (labelled.group("label"), "=", labelled.group("url")) if labelled else cell.partition("=")
        if sep:
            return {"label": label.strip(), "url": url.strip()}
    label = re.sub(r"^https?://(www\.)?", "", cell).split("/")[0] or cell
    return {"label": label, "url": cell}


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
    # newline="" lets the csv module handle \r, \n and \r\n line ends itself, as its docs require.
    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=_sniff_dialect(text))
    try:
        return _parse_rows(reader)
    except csv.Error as exc:
        raise ImportFormatError(f"Invalid CSV near line {reader.line_num}: {exc}") from None


def _parse_rows(reader: csv.DictReader[str]) -> tuple[list[RawRow], list[str]]:
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
    for line_no, rec in numbered_records(reader):
        if not any((v or "").strip() for v in rec.values() if isinstance(v, str)):
            continue
        cell = {k: csv_unescape((v or "").strip()) if isinstance(v, str) else "" for k, v in rec.items() if k}
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
        row = RawRow(number=line_no, data=data, keep_capability_details=bool(present_cap_cols))
        if present_cap_cols:
            row.keep_capability_kinds = [
                k.value for k in CapabilityKind if k.value not in {CAPABILITY_COLUMNS[c] for c in present_cap_cols}
            ]
        if extra_cols:
            row.extra_merge = {c[len(EXTRA_PREFIX) :]: (cell[c] or None) for c in extra_cols}
        rows.append(row)
    return rows, warnings

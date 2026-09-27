import csv
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from appfit.config import CSV_FORMULA_ESCAPE, CSV_FORMULA_START_CHARS, CSV_MULTI_VALUE_SEPARATOR
from appfit.schemas.import_ import RowKind


@dataclass
class RawRow:
    """One record (app, external system or interface) from a file, before validation.

    Only keys present in the file are set; row numbers count within each kind."""

    number: int
    data: dict[str, Any]
    keep_capability_kinds: list[str] = field(default_factory=list)
    # CSV has no details column, so matching capabilities keep the details they have.
    keep_capability_details: bool = False
    extra_merge: dict[str, str | None] | None = None
    kind: RowKind = "app"


class ImportFormatError(ValueError):
    """The file as a whole cannot be parsed."""


def split_multi(value: str) -> list[str]:
    """Cells holding several values separate them with CSV_MULTI_VALUE_SEPARATOR."""
    return [v.strip() for v in value.split(CSV_MULTI_VALUE_SEPARATOR) if v.strip()]


def numbered_records(reader: csv.DictReader[str]) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield each record with the file line it starts on; quoted cells may span several lines."""
    _ = reader.fieldnames  # reads the header, so line_num points past it
    start = reader.line_num + 1
    for rec in reader:
        yield start, rec
        start = reader.line_num + 1


def _needs_escape(value: str) -> bool:
    return value.lstrip(CSV_FORMULA_ESCAPE).startswith(CSV_FORMULA_START_CHARS)


def csv_safe(value: str) -> str:
    """Escape a cell spreadsheets would run as a formula (CSV injection)."""
    return CSV_FORMULA_ESCAPE + value if _needs_escape(value) else value


def csv_unescape(value: str) -> str:
    """Undo csv_safe, so exported files import back unchanged."""
    escaped = value.startswith(CSV_FORMULA_ESCAPE) and _needs_escape(value[1:])
    return value[1:] if escaped else value

from dataclasses import dataclass, field
from typing import Any

from appfit.config import CSV_MULTI_VALUE_SEPARATOR
from appfit.schemas.import_ import RowKind


@dataclass
class RawRow:
    """One record (app, external system or interface) from a file, before validation.

    Only keys present in the file are set; row numbers count within each kind."""

    number: int
    data: dict[str, Any]
    keep_capability_kinds: list[str] = field(default_factory=list)
    extra_merge: dict[str, str | None] | None = None
    kind: RowKind = "app"


class ImportFormatError(ValueError):
    """The file as a whole cannot be parsed."""


def split_multi(value: str) -> list[str]:
    """Cells holding several values separate them with CSV_MULTI_VALUE_SEPARATOR."""
    return [v.strip() for v in value.split(CSV_MULTI_VALUE_SEPARATOR) if v.strip()]

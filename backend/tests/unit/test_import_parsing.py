import codecs
import csv
import json

import pytest

from appfit.services.importer.aliases import normalize_aliases
from appfit.services.importer.parse_csv import parse_csv, parse_link, parse_maintainer
from appfit.services.importer.parse_json import parse_json
from appfit.services.importer.rows import ImportFormatError, csv_safe, csv_unescape


def test_semicolon_csv_in_cp1252_is_detected() -> None:
    content = "name;short_description;tags\nRechnungsprüfung;Prüft Rechnungen;finanzen|rechnungen\n".encode("cp1252")
    rows, warnings = parse_csv(content)
    assert warnings == []
    assert rows[0].data == {
        "name": "Rechnungsprüfung",
        "short_description": "Prüft Rechnungen",
        "tags": ["finanzen", "rechnungen"],
    }


def test_missing_column_is_absent_and_empty_cell_clears() -> None:
    content = b"slug,vendor,tags\nmy-app,,\n"
    rows, _ = parse_csv(content)
    assert rows[0].data == {"slug": "my-app", "vendor": None, "tags": []}
    assert "description" not in rows[0].data


def test_capability_columns_combine_and_remember_absent_kinds() -> None:
    content = b"name,capabilities,features\nX,OCR|Approval workflow,SAP export\n"
    rows, _ = parse_csv(content)
    caps = rows[0].data["capabilities"]
    assert [(c["kind"], c["text"]) for c in caps] == [
        ("capability", "OCR"),
        ("capability", "Approval workflow"),
        ("feature", "SAP export"),
    ]
    assert rows[0].keep_capability_kinds == ["requirement"]


def test_extra_columns_and_unknown_columns() -> None:
    content = b"name,extra.cost_center,colour\nX,4711,red\n"
    rows, warnings = parse_csv(content)
    assert rows[0].extra_merge == {"cost_center": "4711"}
    assert warnings == ["Unknown column ignored: 'colour'"]


def test_utf8_bom_tab_delimited_and_blank_rows() -> None:
    content = codecs.BOM_UTF8 + b"name\tvendor\nA\tACME\n\t\nB\t\n"
    rows, _ = parse_csv(content)
    assert [r.data["name"] for r in rows] == ["A", "B"]
    assert [r.number for r in rows] == [2, 4]


def test_csv_without_name_or_slug_is_rejected() -> None:
    with pytest.raises(ImportFormatError):
        parse_csv(b"vendor\nACME\n")


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("owner:Jane Doe <jane@x.de>", {"role": "owner", "name": "Jane Doe", "kind": "person", "email": "jane@x.de"}),
        ("Team Platform", {"name": "Team Platform", "kind": "team"}),
        ("contact:<ops@x.de>", {"role": "contact", "email": "ops@x.de"}),
    ],
)
def test_parse_maintainer(cell: str, expected: dict[str, str]) -> None:
    assert parse_maintainer(cell) == expected


def test_parse_link() -> None:
    assert parse_link("Wiki=https://wiki.x/a") == {"label": "Wiki", "url": "https://wiki.x/a"}
    assert parse_link("https://www.example.com/docs") == {"label": "example.com", "url": "https://www.example.com/docs"}
    # "=" inside the URL or the label must not move the split.
    assert parse_link("https://wiki.x/page?id=42") == {"label": "wiki.x", "url": "https://wiki.x/page?id=42"}
    assert parse_link("a=b=https://x.de/?q=1") == {"label": "a=b", "url": "https://x.de/?q=1"}
    assert parse_link("Wiki=wiki.x") == {"label": "Wiki", "url": "wiki.x"}


def test_row_numbers_are_file_lines_after_multi_line_cells() -> None:
    rows, _ = parse_csv(b'name,description\nA,"line one\nline two\nline three"\nB,x\n')
    assert [r.number for r in rows] == [2, 5]
    iface_rows, _ = parse_csv(b'from,to,name,description\na,b,X,"one\ntwo"\na,b,Y,\n')
    assert [r.number for r in iface_rows] == [2, 4]


@pytest.mark.parametrize(
    "value", ["=HYPERLINK(1)", "+1", "-x", "@SUM(A1)", "\tx", "'=x", "''-x", "'plain", "plain", ""]
)
def test_formula_cells_are_escaped_and_restored(value: str) -> None:
    escaped = csv_safe(value)
    assert not escaped.startswith(("=", "+", "-", "@", "\t"))
    assert csv_unescape(escaped) == value


def test_json_accepts_document_and_bare_list() -> None:
    doc = {"version": 1, "apps": [{"name": "A"}, {"name": "B", "vendor": None}]}
    rows, _ = parse_json(json.dumps(doc).encode())
    assert [r.data for r in rows] == [{"name": "A"}, {"name": "B", "vendor": None}]
    rows, _ = parse_json(b'[{"name": "C"}]')
    assert rows[0].number == 1


@pytest.mark.parametrize("content", [b"{not json", b'{"version": 2, "apps": []}', b'{"apps": 5}', b"[1]"])
def test_json_format_errors(content: bytes) -> None:
    with pytest.raises(ImportFormatError):
        parse_json(content)


def test_german_aliases() -> None:
    data = normalize_aliases(
        {"lifecycle_status": "Abgekündigt", "license_type": "Open Source", "maintainers": [{"role": "Ansprechpartner"}]}
    )
    assert data["lifecycle_status"] == "deprecated"
    assert data["license_type"] == "oss"
    assert data["maintainers"][0]["role"] == "contact"


def test_carriage_return_line_ends_and_broken_csv() -> None:
    rows, _ = parse_csv(b"name\rA\rB\r")
    assert [r.data["name"] for r in rows] == ["A", "B"]
    too_long = b"name\n" + b"x" * (csv.field_size_limit() + 1) + b"\n"
    with pytest.raises(ImportFormatError, match="Invalid CSV"):
        parse_csv(too_long)

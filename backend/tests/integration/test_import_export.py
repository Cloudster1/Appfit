import json
from collections.abc import Callable

from fastapi.testclient import TestClient

from appfit.models import Role

from .helpers import HTTP_OK, app_payload, create_app

Auth = Callable[[Role], dict[str, str]]

CSV = (
    "slug;name;lifecycle_status;tags;maintainers;capabilities;requirements\n"
    "invoice-hub;Invoice Hub;aktiv;finance|invoices;owner:Jane Doe <jane@corp.local>;OCR|Approval workflow;On-prem\n"
    ";Travel Desk;Pilot;travel;;Flight booking;\n"
).encode("cp1252")


def post_import(client: TestClient, headers: dict[str, str], content: bytes, filename: str, **params: object):  # type: ignore[no-untyped-def]
    return client.post("/api/import", params=params, files={"file": (filename, content)}, headers=headers)


def test_csv_dry_run_then_commit(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    dry = post_import(client, ed, CSV, "apps.csv", dry_run=True)
    assert dry.status_code == HTTP_OK, dry.text
    report = dry.json()
    assert report["committed"] is False
    assert report["stats"]["created"] == 2
    assert client.get("/api/apps", headers=ed).json()["total"] == 0

    real = post_import(client, ed, CSV, "apps.csv", dry_run=False).json()
    assert real["committed"] is True
    assert [i["slug"] for i in real["items"]] == ["invoice-hub", "travel-desk"]
    app = client.get("/api/apps/invoice-hub", headers=ed).json()
    assert app["lifecycle_status"] == "active"
    assert app["maintainers"][0]["email"] == "jane@corp.local"
    assert [(c["kind"], c["text"]) for c in app["capabilities"]] == [
        ("capability", "OCR"),
        ("capability", "Approval workflow"),
        ("requirement", "On-prem"),
    ]
    assert client.get("/api/apps/travel-desk", headers=ed).json()["lifecycle_status"] == "pilot"

    again = post_import(client, ed, CSV, "apps.csv", dry_run=False).json()
    assert again["stats"]["unchanged"] == 2


def test_partial_update_semantics(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Keeper", ["Feature A"], vendor="ACME", description="Long text", tags=["x"]))
    csv = b"slug,vendor,features\nkeeper,,Feature B\n"
    report = post_import(client, ed, csv, "u.csv", dry_run=False).json()
    assert report["items"][0]["action"] == "updated"
    assert set(report["items"][0]["changed_fields"]) == {"vendor", "capabilities"}
    app = client.get("/api/apps/keeper", headers=ed).json()
    assert app["vendor"] is None  # empty cell clears
    assert app["description"] == "Long text"  # missing column keeps
    assert app["tags"] == ["x"]
    # capabilities column absent -> existing capability kind kept, features replaced
    assert [(c["kind"], c["text"]) for c in app["capabilities"]] == [
        ("feature", "Feature B"),
        ("capability", "Feature A"),
    ]


def test_validation_errors_block_everything_unless_skip_invalid(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    doc = {
        "version": 1,
        "apps": [
            {"name": "Good"},
            {"name": "Bad", "homepage_url": "not-a-url"},
            {"name": "Good"},
        ],
    }
    content = json.dumps(doc).encode()
    report = post_import(client, ed, content, "a.json", dry_run=False).json()
    assert report["committed"] is False
    fields = {(e["row"], e["field"]) for e in report["errors"]}
    assert (2, "homepage_url") in fields and (3, "slug") in fields
    assert client.get("/api/apps", headers=ed).json()["total"] == 0

    report = post_import(client, ed, content, "a.json", dry_run=False, skip_invalid=True).json()
    assert report["committed"] is True
    assert report["stats"]["created"] == 1 and report["stats"]["invalid"] == 2


def test_create_only_and_unknown_new_app_without_name(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Existing"))
    content = json.dumps([{"slug": "existing", "vendor": "X"}, {"slug": "ghost", "vendor": "Y"}]).encode()
    report = post_import(client, ed, content, "a.json", dry_run=False, mode="create_only", skip_invalid=True).json()
    actions = {i["slug"]: i["action"] for i in report["items"]}
    assert actions == {"existing": "skipped", "ghost": "invalid"}
    assert "name is required" in report["errors"][0]["message"]


def test_export_round_trip(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(
        client,
        ed,
        app_payload(
            "Round Trip",
            ["Cap one", "Cap two"],
            tags=["t1"],
            tech_stack=["go"],
            extra={"cost_center": "4711"},
            links=[{"label": "Docs", "url": "https://docs.corp/rt"}],
            maintainers=[{"name": "Ann", "email": "ann@corp.local", "role": "owner"}],
        ),
    )
    exported = client.get("/api/export", params={"format": "json"}, headers=ed).json()
    assert exported["version"] == 1 and exported["apps"][0]["slug"] == "round-trip"
    report = post_import(client, ed, json.dumps(exported).encode(), "e.json", dry_run=True).json()
    assert report["stats"]["unchanged"] == 1, report

    csv_resp = client.get("/api/export", params={"format": "csv"}, headers=ed)
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "extra.cost_center" in csv_resp.text.splitlines()[0]
    report = post_import(client, ed, csv_resp.content, "e.csv", dry_run=True).json()
    assert report["stats"]["unchanged"] == 1, report


def test_template_and_schema(client: TestClient, auth: Auth) -> None:
    v = auth(Role.viewer)
    template = client.get("/api/import/template.csv", headers=v)
    assert template.text.startswith("slug,name,")
    report = post_import(client, auth(Role.editor), template.content, "t.csv", dry_run=True).json()
    assert report["errors"] == [] and report["stats"]["created"] == 1
    schema = client.get("/api/import/schema.json", headers=v).json()
    assert "apps" in schema["properties"]


def test_format_errors_and_limits(client: TestClient, auth: Auth, app) -> None:  # type: ignore[no-untyped-def]
    ed = auth(Role.editor)
    assert post_import(client, ed, b"{broken", "x.json").status_code == 400
    app.state.settings.import_max_bytes = 10
    assert post_import(client, ed, CSV, "a.csv").status_code == 400

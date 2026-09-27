from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from appfit.models import Role

from .helpers import HTTP_NO_CONTENT, HTTP_OK, app_payload, create_app, create_iface, iface_payload

Auth = Callable[[Role], dict[str, str]]
HTTP_BAD_REQUEST, HTTP_CONFLICT, HTTP_UNPROCESSABLE = 400, 409, 422


def _apps(client: TestClient, auth: Auth, *names: str, **extra: object) -> None:
    for name in names:
        create_app(client, auth(Role.editor), app_payload(name, **extra))


def test_create_list_update_delete_interface(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "FinanzBuch")
    ed = auth(Role.editor)
    body = iface_payload(
        "belegfix", "finanzbuch", "Buchungsexport", type="file_transfer", data_objects=["Buchungen", "buchungen"]
    )
    created = create_iface(client, ed, body)
    assert created["from"] == {
        "kind": "app",
        "id": created["from"]["id"],
        "name": "Belegfix",
        "slug": "belegfix",
        "lifecycle_status": "active",
    }
    assert created["type"] == "file_transfer"
    assert created["data_objects"] == ["Buchungen"]  # duplicates ignoring case are dropped
    assert created["indexed"] is False

    listed = client.get("/api/interfaces", params={"app": "finanzbuch"}, headers=auth(Role.viewer)).json()
    assert [i["name"] for i in listed] == ["Buchungsexport"]

    changed = client.put(
        f"/api/interfaces/{created['id']}",
        json={**body, "status": "planned", "bidirectional": True},
        headers=ed,
    )
    assert changed.status_code == HTTP_OK and changed.json()["status"] == "planned"

    detail = client.get("/api/apps/finanzbuch", headers=auth(Role.viewer)).json()
    assert detail["interfaces"] == [
        {
            "id": created["id"],
            "name": "Buchungsexport",
            "direction": "both",
            "counterpart": created["from"],
            "type": "file_transfer",
            "data_objects": ["Buchungen"],
            "frequency": None,
            "status": "planned",
        }
    ]

    assert client.delete(f"/api/interfaces/{created['id']}", headers=ed).status_code == HTTP_NO_CONTENT
    assert client.get("/api/interfaces", headers=ed).json() == []


def test_external_systems_are_reused_by_name_and_protected_while_used(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "TravelDesk")
    ed = auth(Role.editor)
    create_iface(client, ed, iface_payload("belegfix", "system:SAP S/4HANA", "Rechnungen an SAP"))
    create_iface(client, ed, iface_payload("traveldesk", "system:sap s/4hana", "Spesen an SAP"))
    systems = client.get("/api/external-systems", headers=auth(Role.viewer)).json()
    assert [(s["name"], s["interface_count"]) for s in systems] == [("SAP S/4HANA", 2)]

    resp = client.delete(f"/api/external-systems/{systems[0]['id']}", headers=auth(Role.admin))
    assert resp.status_code == HTTP_CONFLICT
    assert "used by 2 interface" in resp.json()["detail"]


def test_endpoint_validation(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix")
    ed = auth(Role.editor)

    def post(body: dict[str, object]) -> int:
        return client.post("/api/interfaces", json=body, headers=ed).status_code

    assert post(iface_payload("belegfix", "belegfix", "Loop")) == HTTP_UNPROCESSABLE
    assert post(iface_payload("system:SAP", "system:DATEV", "Between systems")) == HTTP_UNPROCESSABLE
    assert post({"from": {"app": "belegfix", "system": "SAP"}, "to": {"system": "DATEV"}, "name": "x"}) == (
        HTTP_UNPROCESSABLE
    )
    assert post(iface_payload("belegfix", "missing-app", "Unknown")) == HTTP_BAD_REQUEST
    create_iface(client, ed, iface_payload("belegfix", "system:SAP", "Export"))
    assert post(iface_payload("belegfix", "system:sap", "EXPORT")) == HTTP_CONFLICT


def test_deleting_an_app_removes_its_interfaces_and_updates_the_neighbour(
    client: TestClient, auth: Auth, db: Session
) -> None:
    _apps(client, auth, "Belegfix", "FinanzBuch")
    create_iface(client, auth(Role.editor), iface_payload("belegfix", "finanzbuch", "Kreditorenexport"))
    tsv = text("SELECT search_tsv @@ plainto_tsquery('german', 'Kreditorenexport') FROM apps WHERE slug = :s")
    assert db.scalar(tsv, {"s": "finanzbuch"}) is True

    assert client.delete("/api/apps/belegfix", headers=auth(Role.admin)).status_code == HTTP_NO_CONTENT
    assert client.get("/api/interfaces", headers=auth(Role.viewer)).json() == []
    assert db.scalar(tsv, {"s": "finanzbuch"}) is False


def test_catalog_keyword_search_finds_apps_by_interface_counterpart(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "Wiki")
    create_iface(client, auth(Role.editor), iface_payload("belegfix", "system:DATEV", "Buchungsstapel"))
    page = client.get("/api/apps", params={"q": "DATEV"}, headers=auth(Role.viewer)).json()
    assert [i["slug"] for i in page["items"]] == ["belegfix"]


def test_renaming_an_app_or_system_makes_interface_texts_stale(
    client: TestClient, auth: Auth, run_worker: Callable[[], int]
) -> None:
    _apps(client, auth, "Belegfix")
    ed = auth(Role.editor)
    iface = create_iface(client, ed, iface_payload("belegfix", "system:SAP", "Export"))
    run_worker()
    assert client.get(f"/api/interfaces/{iface['id']}", headers=ed).json()["indexed"] is True

    system_id = client.get("/api/external-systems", headers=ed).json()[0]["id"]
    resp = client.put(f"/api/external-systems/{system_id}", json={"name": "SAP S/4HANA"}, headers=ed)
    assert resp.status_code == HTTP_OK
    assert client.get(f"/api/interfaces/{iface['id']}", headers=ed).json()["indexed"] is False
    run_worker()

    # Each side's text names the other side, so renaming the counterpart app makes it stale too.
    _apps(client, auth, "FinanzBuch")
    to_ledger = create_iface(client, ed, iface_payload("finanzbuch", "belegfix", "Buchungen"))
    run_worker()
    client.put("/api/apps/belegfix", json=app_payload("Belegfix Pro"), headers=ed)
    assert client.get(f"/api/interfaces/{to_ledger['id']}", headers=ed).json()["indexed"] is False


def test_landscape_filters(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "FinanzBuch", domains=["finance"])
    _apps(client, auth, "TalentScout", "Onboardly", domains=["hr"])
    _apps(client, auth, "Old Portal", lifecycle_status="retired")
    ed = auth(Role.editor)
    create_iface(client, ed, iface_payload("belegfix", "finanzbuch", "Buchungen", type="file_transfer"))
    create_iface(client, ed, iface_payload("talentscout", "onboardly", "Bewerber", type="rest_api", status="planned"))
    create_iface(client, ed, iface_payload("belegfix", "system:SAP", "Export", type="rest_api"))
    create_iface(client, ed, iface_payload("old-portal", "belegfix", "Altdaten"))
    viewer = auth(Role.viewer)

    def names(**params: object) -> tuple[list[str], list[str]]:
        data = client.get("/api/landscape", params=params, headers=viewer).json()
        return sorted(n["name"] for n in data["nodes"]), sorted(e["name"] for e in data["edges"])

    # Retired apps and their interfaces are hidden by default.
    assert names() == (
        ["Belegfix", "FinanzBuch", "Onboardly", "SAP", "TalentScout"],
        ["Bewerber", "Buchungen", "Export"],
    )
    assert names(domain="finance") == (["Belegfix", "FinanzBuch", "SAP"], ["Buchungen", "Export"])
    assert names(type="rest_api", include_systems=False) == (["Onboardly", "TalentScout"], ["Bewerber"])
    assert names(status="planned") == (["Onboardly", "TalentScout"], ["Bewerber"])

    data = client.get("/api/landscape", params={"domain": "finance"}, headers=viewer).json()
    belegfix = next(n for n in data["nodes"] if n["name"] == "Belegfix")
    assert belegfix == {
        "id": belegfix["id"],
        "kind": "app",
        "name": "Belegfix",
        "slug": "belegfix",
        "lifecycle_status": "active",
        "domains": ["finance"],
        "degree": 2,
    }
    edge = next(e for e in data["edges"] if e["name"] == "Export")
    assert edge["source"] == belegfix["id"] and edge["target"].startswith("system:")


def post_import(client: TestClient, headers: dict[str, str], content: bytes, filename: str, **params: object) -> dict:  # type: ignore[type-arg]
    resp = client.post("/api/import", files={"file": (filename, content)}, params=params, headers=headers)
    assert resp.status_code == HTTP_OK, resp.text
    return resp.json()  # type: ignore[no-any-return]


JSON_DOC = {
    "version": 1,
    "interfaces": [
        {"from": {"app": "belegfix"}, "to": {"app": "finanzbuch"}, "name": "Buchungsstapel", "type": "Datei"},
        {"from": {"app": "belegfix"}, "to": {"system": "DATEV"}, "name": "Export", "status": "geplant"},
    ],
    "external_systems": [{"name": "DATEV", "vendor": "DATEV eG"}],
    "apps": [{"name": "Belegfix"}, {"name": "FinanzBuch"}],
}


def test_json_import_resolves_apps_of_the_same_file_and_round_trips(client: TestClient, auth: Auth) -> None:
    import json

    ed = auth(Role.editor)
    content = json.dumps(JSON_DOC).encode()
    dry = post_import(client, ed, content, "catalog.json")
    assert dry["committed"] is False and dry["errors"] == []
    assert [(i["kind"], i["action"]) for i in dry["items"]] == [
        ("app", "created"),
        ("app", "created"),
        ("system", "created"),
        ("interface", "created"),
        ("interface", "created"),
    ]
    assert client.get("/api/interfaces", headers=ed).json() == []  # the dry run wrote nothing

    done = post_import(client, ed, content, "catalog.json", dry_run=False)
    assert done["committed"] is True
    ifaces = {i["name"]: i for i in client.get("/api/interfaces", headers=ed).json()}
    assert ifaces["Buchungsstapel"]["type"] == "file_transfer"
    assert ifaces["Export"]["status"] == "planned"
    assert client.get("/api/external-systems", headers=ed).json()[0]["vendor"] == "DATEV eG"

    exported = client.get("/api/export", params={"format": "json"}, headers=ed).content
    again = post_import(client, ed, exported, "export.json", dry_run=False)
    assert {i["action"] for i in again["items"]} == {"unchanged"}


def test_interface_csv_with_german_aliases_partial_update_and_round_trip(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "FinanzBuch")
    ed = auth(Role.editor)
    csv_text = (
        "from;to;name;type;data_objects;frequency;status;bidirectional\r\n"
        "belegfix;app:finanzbuch;Buchungsstapel;Datei;Buchungen|Belege;Nachtlauf;aktiv;nein\r\n"
        "app:belegfix;system:SAP S/4HANA;Rechnungen;REST;Rechnungen;Echtzeit;geplant;ja\r\n"
    )
    report = post_import(client, ed, csv_text.encode("cp1252"), "ifaces.csv", dry_run=False)
    assert report["errors"] == [] and report["stats"]["created"] == 2
    sap = next(i for i in client.get("/api/interfaces", headers=ed).json() if i["name"] == "Rechnungen")
    assert (sap["type"], sap["frequency"], sap["status"], sap["bidirectional"]) == (
        "rest_api",
        "realtime",
        "planned",
        True,
    )
    assert sap["to"]["kind"] == "system" and sap["to"]["name"] == "SAP S/4HANA"

    # Missing columns keep the stored values.
    partial = post_import(client, ed, b"from,to,name,status\nbelegfix,system:SAP S/4HANA,Rechnungen,aktiv\n", "p.csv")
    assert partial["items"][0]["action"] == "updated"
    assert partial["items"][0]["changed_fields"] == ["status"]

    exported = client.get("/api/export", params={"format": "csv", "kind": "interfaces"}, headers=ed).content
    assert exported.startswith(b"from,to,name,type,")
    again = post_import(client, ed, exported, "roundtrip.csv", dry_run=False)
    assert {i["action"] for i in again["items"]} == {"unchanged"}


def test_interface_import_errors_block_or_skip(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix")
    ed = auth(Role.editor)
    content = (
        b"from,to,name,type\nbelegfix,system:SAP,Good,rest\nbelegfix,missing-app,Bad,rest\nbelegfix,system:SAP,,x\n"
    )
    blocked = post_import(client, ed, content, "i.csv", dry_run=False)
    assert blocked["committed"] is False
    assert {(e["row"], e["kind"], e["field"]) for e in blocked["errors"]} == {
        (4, "interface", "name"),
        (4, "interface", "type"),
    }

    skipped = post_import(client, ed, content, "i.csv", dry_run=False, skip_invalid=True)
    assert skipped["committed"] is True
    assert [(i["row"], i["action"]) for i in skipped["items"]] == [(2, "created"), (3, "invalid")]
    assert "Unknown app 'missing-app'" in {e["message"] for e in skipped["errors"]}
    assert [i["name"] for i in client.get("/api/interfaces", headers=ed).json()] == ["Good"]


def test_interfaces_csv_template_imports_cleanly(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Invoice Hub", "HR Portal")
    ed = auth(Role.editor)
    template = client.get("/api/import/interfaces-template.csv", headers=ed).content
    report = post_import(client, ed, template, "template.csv")
    assert report["errors"] == [] and report["stats"]["created"] == 2


def test_renaming_an_app_refreshes_its_neighbours_keyword_search(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "Belegfix", "Legacy CRM")
    ed = auth(Role.editor)
    create_iface(client, ed, iface_payload("belegfix", "legacy-crm", "Kundenstamm"))
    client.put("/api/apps/legacy-crm", json=app_payload("SalesHub"), headers=ed)

    def found(q: str) -> list[str]:
        return [i["slug"] for i in client.get("/api/apps", params={"q": q}, headers=ed).json()["items"]]

    assert "belegfix" in found("SalesHub")
    assert "belegfix" not in found("Legacy")


def test_an_app_and_a_system_with_the_same_name_are_distinct_import_endpoints(client: TestClient, auth: Auth) -> None:
    _apps(client, auth, "DATEV", "HR")
    content = b"from,to,name,type\ndatev,hr,Export,rest_api\nsystem:DATEV,hr,Export,rest_api\n"
    report = post_import(client, auth(Role.editor), content, "i.csv", dry_run=False)
    assert report["errors"] == [] and report["stats"]["created"] == 2


def test_embedding_and_reindex_keep_updated_at(
    client: TestClient, auth: Auth, db: Session, run_worker: Callable[[], int]
) -> None:
    _apps(client, auth, "Belegfix")
    ed = auth(Role.editor)
    iface = create_iface(client, ed, iface_payload("belegfix", "system:SAP", "Export"))
    # now() is fixed within the test transaction, so backdate the rows to make a bump visible.
    old = "2020-01-01T00:00:00Z"
    for table in ("apps", "interfaces"):
        db.execute(text(f"UPDATE {table} SET updated_at = :old"), {"old": old})
    db.commit()

    run_worker()
    resp = client.post("/api/admin/embeddings/reindex", json={"scope": "all"}, headers=auth(Role.admin))
    assert resp.status_code == HTTP_OK, resp.text
    run_worker()

    app_after = client.get("/api/apps/belegfix", headers=ed).json()
    iface_after = client.get(f"/api/interfaces/{iface['id']}", headers=ed).json()
    assert app_after["embedding_status"] == "indexed" and iface_after["indexed"] is True
    assert {app_after["updated_at"][:10], iface_after["updated_at"][:10]} == {"2020-01-01"}

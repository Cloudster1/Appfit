from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from appfit.models import AppCapability, Role

from .helpers import HTTP_NO_CONTENT, HTTP_OK, app_payload, create_app

Auth = Callable[[Role], dict[str, str]]


def test_create_get_and_list(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    payload = app_payload(
        "Invoice Hub",
        ["OCR extraction", "Approval workflow"],
        tags=["Finance", "finance", " Invoices "],
        tech_stack=["Java"],
        maintainers=[
            {"name": "Jane Doe", "email": "jane@corp.local", "role": "owner"},
            {"name": "Team Finance IT", "kind": "team"},
        ],
        links=[{"label": "Wiki", "url": "https://wiki.corp/invoice"}],
        license_type="commercial",
    )
    app = create_app(client, ed, payload)
    assert app["slug"] == "invoice-hub"
    assert app["tags"] == ["finance", "invoices"]
    assert app["tech_stack"] == ["java"]
    assert [m["role"] for m in app["maintainers"]] == ["owner", "maintainer"]
    assert [c["text"] for c in app["capabilities"]] == ["OCR extraction", "Approval workflow"]
    assert app["embedding_status"] == "pending"

    got = client.get("/api/apps/invoice-hub", headers=auth(Role.viewer))
    assert got.status_code == HTTP_OK and got.json()["id"] == app["id"]

    create_app(client, ed, app_payload("Invoice Hub"))  # same name -> suffixed slug
    page = client.get("/api/apps", params={"q": "invoice"}, headers=auth(Role.viewer)).json()
    assert page["total"] == 2
    assert {i["slug"] for i in page["items"]} == {"invoice-hub", "invoice-hub-2"}
    filtered = client.get("/api/apps", params={"tags": "finance", "maintainer": "jane"}, headers=auth(Role.viewer))
    assert [i["slug"] for i in filtered.json()["items"]] == ["invoice-hub"]


def test_fts_matches_capability_text_in_german(client: TestClient, auth: Auth) -> None:
    create_app(client, auth(Role.editor), app_payload("Tool A", ["Automatische Freigabe von Rechnungen"]))
    create_app(client, auth(Role.editor), app_payload("Tool B", ["Newsletter versenden"]))
    page = client.get("/api/apps", params={"q": "Rechnung", "sort": "relevance"}, headers=auth(Role.viewer)).json()
    assert [i["name"] for i in page["items"]] == ["Tool A"]


def test_put_keeps_unchanged_capabilities_and_their_embeddings(
    client: TestClient, auth: Auth, db: Session, run_worker: Callable[[], int]
) -> None:
    ed = auth(Role.editor)
    app = create_app(client, ed, app_payload("Doc Vault", ["Full text search", "Versioning", "Retention policies"]))
    assert run_worker() == 4  # 1 summary + 3 capabilities
    ids = {c["text"]: c["id"] for c in app["capabilities"]}

    payload = app_payload("Doc Vault", [], short_description=app["short_description"])
    payload["capabilities"] = [
        {"text": "Retention policies"},  # moved, unchanged
        {"id": ids["Versioning"], "text": "Versioning of documents"},  # edited by id
        {"text": "Legal hold"},  # new
    ]
    resp = client.put("/api/apps/doc-vault", json=payload, headers=ed)
    assert resp.status_code == HTTP_OK, resp.text
    caps = resp.json()["capabilities"]
    assert [c["text"] for c in caps] == ["Retention policies", "Versioning of documents", "Legal hold"]
    assert caps[0]["id"] == ids["Retention policies"] and caps[0]["indexed"] is True
    assert caps[1]["id"] == ids["Versioning"] and caps[1]["indexed"] is False
    assert caps[2]["indexed"] is False
    assert db.scalar(select(AppCapability).where(AppCapability.id == ids["Full text search"])) is None
    assert resp.json()["embedding_status"] == "pending"
    assert run_worker() == 2
    assert client.get("/api/apps/doc-vault", headers=ed).json()["embedding_status"] == "indexed"


def test_put_with_rename_to_existing_text_does_not_violate_unique_index(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    app = create_app(client, ed, app_payload("Swap", ["alpha", "beta"]))
    a, b = (c["id"] for c in app["capabilities"])
    payload = app_payload("Swap", [])
    payload["capabilities"] = [{"id": a, "text": "beta"}, {"id": b, "text": "alpha"}]
    resp = client.put("/api/apps/swap", json=payload, headers=ed)
    assert resp.status_code == HTTP_OK, resp.text
    assert [c["text"] for c in resp.json()["capabilities"]] == ["beta", "alpha"]


def test_summary_and_tsv_refresh_on_update(
    client: TestClient, auth: Auth, db: Session, run_worker: Callable[[], int]
) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Planner", ["Gantt charts"]))
    run_worker()
    payload = app_payload("Planner", ["Gantt charts"], description="Kapazitätsplanung für Teams")
    client.put("/api/apps/planner", json=payload, headers=ed)
    tsv = db.execute(text("SELECT search_tsv::text FROM apps WHERE slug = 'planner'")).scalar_one()
    assert "kapazitatsplan" in tsv or "kapazitätsplanung" in tsv
    status = client.get("/api/apps/planner", headers=ed).json()
    assert status["embedding_status"] == "pending"
    assert status["capabilities"][0]["indexed"] is True
    assert run_worker() == 1


def test_validation_and_conflicts(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    assert client.post("/api/apps", json={"name": ""}, headers=ed).status_code == 422
    assert client.post("/api/apps", json={"name": "X", "homepage_url": "ftp://x"}, headers=ed).status_code == 422
    assert client.post("/api/apps", json={"name": "X", "slug": "Bad Slug"}, headers=ed).status_code == 422
    create_app(client, ed, app_payload("X", slug="taken"))
    assert client.post("/api/apps", json={"name": "Y", "slug": "taken"}, headers=ed).status_code == 409
    create_app(client, ed, app_payload("Z"))
    assert client.put("/api/apps/z", json={"name": "Z", "slug": "taken"}, headers=ed).status_code == 409
    assert client.get("/api/apps/missing", headers=ed).status_code == 404


def test_duplicate_capabilities_are_removed(client: TestClient, auth: Auth) -> None:
    app = create_app(client, auth(Role.editor), app_payload("Dup", ["Same", "same ", "Other"]))
    assert [c["text"] for c in app["capabilities"]] == ["Same", "Other"]


def test_delete_and_similar(client: TestClient, auth: Auth, run_worker: Callable[[], int]) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Invoice Scanner", ["Invoice OCR"], description="Scans invoices"))
    create_app(client, ed, app_payload("Invoice Approver", ["Invoice approval"], description="Approves invoices"))
    create_app(client, ed, app_payload("Chat", ["Team chat"], description="Messaging for teams"))
    run_worker()
    similar = client.get("/api/apps/invoice-scanner/similar", headers=ed).json()
    assert similar[0]["slug"] == "invoice-approver"
    assert client.delete("/api/apps/chat", headers=ed).status_code == 403
    assert client.delete("/api/apps/chat", headers=auth(Role.admin)).status_code == HTTP_NO_CONTENT
    assert client.get("/api/apps/chat", headers=ed).status_code == 404


def test_tags_rename_merge_delete(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("A", tags=["fin", "finance"]))
    create_app(client, ed, app_payload("B", tags=["fin"]))
    tags = {t["name"]: t for t in client.get("/api/tags", headers=ed).json()}
    assert tags["fin"]["app_count"] == 2
    merged = client.patch(f"/api/tags/{tags['fin']['id']}", json={"merge_into": tags["finance"]["id"]}, headers=ed)
    assert merged.json()["app_count"] == 2
    assert client.get("/api/apps/a", headers=ed).json()["tags"] == ["finance"]
    renamed = client.patch(f"/api/tags/{tags['finance']['id']}", json={"name": "Finanzen"}, headers=ed)
    assert renamed.json()["name"] == "finanzen"
    assert client.delete(f"/api/tags/{tags['finance']['id']}", headers=ed).status_code == HTTP_NO_CONTENT
    assert client.get("/api/apps/b", headers=ed).json()["tags"] == []


def test_maintainers_crud(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    m = client.post(
        "/api/maintainers", json={"name": "Ops Team", "kind": "team", "email": "ops@corp.local"}, headers=ed
    ).json()
    assert (
        client.post("/api/maintainers", json={"name": "Other", "email": "ops@corp.local"}, headers=ed).status_code
        == 409
    )
    app = create_app(client, ed, app_payload("Runbook", maintainers=[{"id": m["id"], "role": "owner"}]))
    assert app["maintainers"][0]["name"] == "Ops Team"
    assert client.get("/api/maintainers", params={"q": "ops"}, headers=ed).json()[0]["id"] == m["id"]
    assert client.delete(f"/api/maintainers/{m['id']}", headers=ed).status_code == HTTP_NO_CONTENT
    assert client.get("/api/apps/runbook", headers=ed).json()["maintainers"] == []


def _facet_map(values: list[dict[str, object]]) -> dict[object, object]:
    return {v["value"]: v["count"] for v in values}


def test_facets_count_each_dimension_without_its_own_selection(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Ledger", domains=["finance"], license_type="commercial"))
    create_app(client, ed, app_payload("Payroll", domains=["finance", "hr"], license_type="internal"))
    create_app(client, ed, app_payload("Recruit", domains=["hr"], lifecycle_status="pilot"))
    create_app(client, ed, app_payload("Old Books", domains=["finance"], lifecycle_status="retired"))
    viewer = auth(Role.viewer)

    facets = client.get("/api/apps/facets", headers=viewer).json()
    assert _facet_map(facets["domain"]) == {"finance": 3, "hr": 2}
    assert _facet_map(facets["lifecycle"]) == {"active": 2, "pilot": 1, "retired": 1}
    assert _facet_map(facets["license_type"]) == {"commercial": 1, "internal": 1}
    assert facets["domain"][0]["value"] == "finance"  # most common first

    selected = client.get("/api/apps/facets", params={"domain": "hr", "status": "active"}, headers=viewer).json()
    # Domain counts ignore the domain selection but respect the lifecycle one, and vice versa.
    assert _facet_map(selected["domain"]) == {"finance": 2, "hr": 1}
    assert _facet_map(selected["lifecycle"]) == {"active": 1, "pilot": 1}


def test_domain_filter_matches_any_selected_domain(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Ledger", domains=["finance"]))
    create_app(client, ed, app_payload("Recruit", domains=["hr"]))
    create_app(client, ed, app_payload("Wiki", tags=["finance"]))  # a general tag is not a domain
    page = client.get("/api/apps", params={"domain": ["finance", "HR"]}, headers=auth(Role.viewer)).json()
    assert [i["slug"] for i in page["items"]] == ["ledger", "recruit"]

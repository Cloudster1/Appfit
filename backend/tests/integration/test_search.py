import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from appfit.ml.fake_embedder import FakeEmbedder
from appfit.models import Role
from appfit.services.search.retrieval import FilterSpec, capability_ranking, filter_conditions

from .helpers import HTTP_NO_CONTENT, HTTP_OK, SAMPLE_CATALOG, app_payload, create_app, create_iface, iface_payload

Auth = Callable[[Role], dict[str, str]]


@pytest.fixture
def catalog(client: TestClient, auth: Auth, run_worker: Callable[[], int]) -> None:
    for payload in SAMPLE_CATALOG:
        create_app(client, auth(Role.editor), payload)
    run_worker()


def search(client: TestClient, headers: dict[str, str], **body: object) -> dict:  # type: ignore[type-arg]
    resp = client.post("/api/search", json=body, headers=headers)
    assert resp.status_code == HTTP_OK, resp.text
    return resp.json()  # type: ignore[no-any-return]


@pytest.mark.usefixtures("catalog")
def test_parse_endpoint(client: TestClient, auth: Auth) -> None:
    resp = client.post("/api/search/parse", json={"text": "Must:\n- SSO\n- Audit log"}, headers=auth(Role.viewer))
    assert [(r["text"], r["priority"]) for r in resp.json()["requirements"]] == [("SSO", "must"), ("Audit log", "must")]


@pytest.mark.usefixtures("catalog")
def test_search_ranks_the_matching_app_first_with_evidence(client: TestClient, auth: Auth) -> None:
    text = "- OCR extraction of invoice data\n- approval workflow for invoices\n- export invoices to SAP"
    res = search(client, auth(Role.viewer), text=text)
    assert res["status"] == "ok"
    top = res["results"][0]
    assert top["app"]["slug"] == "invoice-hub"
    assert top["label"] == "strong"
    assert [e["status"] for e in top["evidence"]] == ["covered", "covered", "covered"]
    assert top["evidence"][2]["capability"]["text"] == "Export of booked invoices to SAP FI"
    assert "sap" in top["evidence"][2]["keyword_hits"]
    assert top["signals"]["capability_rank"] == 1
    assert res["search_log_id"]


@pytest.mark.usefixtures("catalog")
def test_retired_apps_are_excluded_by_default(client: TestClient, auth: Auth) -> None:
    res = search(client, auth(Role.viewer), text="sending newsletters by email")
    assert all(r["app"]["slug"] != "old-mailer" for r in res["results"])
    res = search(client, auth(Role.viewer), text="sending newsletters by email", filters={"lifecycle": ["retired"]})
    assert res["results"][0]["app"]["slug"] == "old-mailer"


@pytest.mark.usefixtures("catalog")
def test_no_match_and_catalog_gaps(client: TestClient, auth: Auth) -> None:
    res = search(client, auth(Role.viewer), text="- quantum chromodynamics simulation\n- telescope scheduling")
    assert res["status"] == "no_match"
    assert res["catalog_gaps"] == [0, 1]
    assert all(r["recommended"] is False for r in res["results"])


@pytest.mark.usefixtures("catalog")
def test_partial_match_reports_gaps_and_must_have_penalty(client: TestClient, auth: Auth) -> None:
    reqs = [
        {"text": "travel expense reports with receipt upload"},
        {"text": "quantum chromodynamics simulation", "priority": "must"},
    ]
    res = search(client, auth(Role.viewer), requirements=reqs)
    travel = next(r for r in res["results"] if r["app"]["slug"] == "travel-desk")
    assert [e["status"] for e in travel["evidence"]] == ["covered", "gap"]
    assert "missing_must_have" in travel["flags"]
    assert res["catalog_gaps"] == [1]


@pytest.mark.usefixtures("catalog")
def test_filters_by_tag(client: TestClient, auth: Auth) -> None:
    res = search(client, auth(Role.viewer), text="document archive with full text search", filters={"tags": ["hr"]})
    assert all(r["app"]["slug"] == "travel-desk" for r in res["results"])


def test_search_requires_input_and_loaded_model(client: TestClient, auth: Auth, app) -> None:  # type: ignore[no-untyped-def]
    v = auth(Role.viewer)
    assert client.post("/api/search", json={"text": "  "}, headers=v).status_code == 422
    app.state.embedder = None
    resp = client.post("/api/search", json={"text": "x"}, headers=v)
    assert resp.status_code == 503
    assert "loading" in resp.json()["detail"]


@pytest.mark.usefixtures("catalog")
def test_feedback_and_admin_logs(client: TestClient, auth: Auth) -> None:
    res = search(client, auth(Role.viewer), text="booking of flights")
    fb = client.post(
        f"/api/search/{res['search_log_id']}/feedback",
        json={"rating": "down", "expected_app_slug": "travel-desk"},
        headers=auth(Role.viewer),
    )
    assert fb.status_code == HTTP_NO_CONTENT
    logs = client.get("/api/admin/search-logs", params={"only_feedback": True}, headers=auth(Role.admin)).json()
    assert logs["total"] == 1
    assert logs["items"][0]["feedback"]["rating"] == "down"


def test_result_tags_are_unique_when_a_tag_and_a_domain_share_a_name(
    client: TestClient, auth: Auth, run_worker: Callable[[], int]
) -> None:
    # Regression: the same name as tag and domain rendered twice in result cards.
    payload = app_payload("Team Chat", ["Team chat with channels"], tags=["collaboration"], domains=["collaboration"])
    create_app(client, auth(Role.editor), payload)
    run_worker()
    res = search(client, auth(Role.viewer), text="team chat with channels")
    app = next(r["app"] for r in res["results"] if r["app"]["slug"] == "team-chat")
    assert app["tags"] == ["collaboration"]


def test_results_carry_domains_and_owner_first(client: TestClient, auth: Auth, run_worker: Callable[[], int]) -> None:
    payload = app_payload(
        "Team Chat",
        ["Team chat with channels"],
        domains=["collaboration"],
        maintainers=[
            {"name": "Alex Admin", "role": "contact"},
            {"name": "Workplace Team", "kind": "team", "role": "owner"},
        ],
    )
    create_app(client, auth(Role.editor), payload)
    run_worker()
    app = search(client, auth(Role.viewer), text="team chat with channels")["results"][0]["app"]
    assert app["domains"] == ["collaboration"]
    assert app["maintainers"] == ["Workplace Team", "Alex Admin"]


@pytest.mark.usefixtures("catalog")
def test_search_domain_filter_matches_any_selected_domain(client: TestClient, auth: Auth) -> None:
    text = "- approval of requests by managers"
    res = search(client, auth(Role.viewer), text=text, filters={"domains": ["travel", "nothing"]})
    assert {r["app"]["slug"] for r in res["results"]} == {"travel-desk"}


def test_interface_evidence_connections_and_combinations(
    client: TestClient, auth: Auth, run_worker: Callable[[], int]
) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Belegfix", ["Rechnungen per OCR auslesen"]))
    create_app(client, ed, app_payload("FinanzBuch", ["Kreditorenbuchhaltung mit Zahlungsvorschlag"]))
    create_app(client, ed, app_payload("Wiki", ["Seiten gemeinsam bearbeiten"]))
    for body in (
        iface_payload("belegfix", "finanzbuch", "Buchungsstapel", type="file_transfer"),
        iface_payload("belegfix", "system:DATEV", "Export Buchungsstapel DATEV", status="planned"),
        iface_payload("finanzbuch", "system:DATEV", "DATEV Meldungen"),
        iface_payload("wiki", "system:DATEV", "Export Buchungsstapel DATEV", status="deprecated"),
    ):
        create_iface(client, ed, body)
    run_worker()

    text = "- Rechnungen per OCR auslesen\n- Kreditorenbuchhaltung mit Zahlungsvorschlag\n- Export Buchungsstapel DATEV"
    res = search(client, auth(Role.viewer), text=text)
    by_slug = {r["app"]["slug"]: r for r in res["results"]}
    datev = by_slug["belegfix"]["evidence"][2]
    assert datev["via"] == "interface" and datev["capability"] is None
    assert datev["status"] == "partial"  # planned interfaces are capped below "covered"
    assert datev["interface"]["name"] == "Export Buchungsstapel DATEV"
    assert datev["interface"]["counterpart"]["name"] == "DATEV"
    assert "wiki" not in by_slug  # deprecated interfaces are not evidence

    nodes = {n["name"]: n for n in res["connections"]["nodes"]}
    assert {"Belegfix", "FinanzBuch", "DATEV"} <= set(nodes)  # DATEV is shared by two result apps
    assert {e["name"] for e in res["connections"]["edges"]} == {
        "Buchungsstapel",
        "Export Buchungsstapel DATEV",
        "DATEV Meldungen",
    }
    assert res["combinations"][0]["apps"] == ["belegfix", "finanzbuch"]
    assert res["combinations"][0]["covered"] == [0, 1]
    assert res["combinations"][0]["interface_name"] == "Buchungsstapel"


def test_interface_hits_are_limited_to_apps_passing_the_filters(
    client: TestClient, auth: Auth, run_worker: Callable[[], int], db: Session, embedder: FakeEmbedder
) -> None:
    ed = auth(Role.editor)
    create_app(client, ed, app_payload("Alpha", domains=["other"]))
    beta = create_app(client, ed, app_payload("Beta", domains=["finance"]))
    create_iface(client, ed, iface_payload("alpha", "system:SAP", "Rechnungen an SAP buchen"))
    create_iface(client, ed, iface_payload("beta", "system:SAP", "Rechnungen buchen"))
    run_worker()

    # Alpha's interface is the closest overall, but only Beta passes the domain filter.
    vecs = embedder.embed_queries(["Rechnungen an SAP buchen - Integration mit SAP"])
    conds = filter_conditions(FilterSpec(domains=["finance"]))
    assert capability_ranking(db, vecs, [1.0], conds, embedder.model_id, 1) == [uuid.UUID(beta["id"])]

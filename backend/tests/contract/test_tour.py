"""A realistic walk through every API operation; each response must match the OpenAPI spec."""

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx
import schemathesis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from appfit.models import Role, User
from tests.conftest import TEST_PASSWORD

Auth = Callable[[Role], dict[str, str]]
OK, CREATED, NO_CONTENT = 200, 201, 204


class SpecClient:
    """Sends requests as one role and validates every response against the operation it hits."""

    def __init__(self, client: TestClient, schema: Any, headers: dict[str, str]) -> None:
        self.client, self.schema, self.headers = client, schema, headers
        self.covered: set[str] = set()

    def call(self, method: str, path: str, expect: int = OK, **kwargs: Any) -> httpx.Response:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        resp = self.client.request(method, path, headers=headers, **kwargs)
        assert resp.status_code == expect, f"{method} {path}: {resp.status_code} {resp.text[:500]}"
        operation = self.schema.find_operation_by_path(method, urlsplit(path).path)
        assert operation is not None, f"{method} {path} is not in the spec"
        operation.validate_response(resp)
        self.covered.add(operation.label)
        return resp

    def json(self, method: str, path: str, expect: int = OK, **kwargs: Any) -> Any:
        return self.call(method, path, expect, **kwargs).json()


def test_every_operation_works_and_matches_the_spec(
    app: FastAPI, client: TestClient, auth: Auth, users: dict[Role, User], run_worker: Callable[[], int]
) -> None:
    schema = schemathesis.openapi.from_asgi("/api/openapi.json", app)
    api = SpecClient(client, schema, auth(Role.admin))

    # Health, auth, meta
    api.call("GET", "/api/health")
    api.call("GET", "/api/health/ready")
    login = {"email": users[Role.viewer].email, "password": TEST_PASSWORD}
    token = api.json("POST", "/api/auth/login", json=login)["access_token"]
    assert api.json("GET", "/api/auth/me", headers={"Authorization": f"Bearer {token}"})["role"] == "viewer"
    api.call("POST", "/api/auth/logout", NO_CONTENT)
    change = {"current_password": TEST_PASSWORD, "new_password": "another-long-password"}
    api.call("POST", "/api/auth/change-password", NO_CONTENT, json=change, headers=auth(Role.editor))
    assert "interface_type" in api.json("GET", "/api/meta/enums")
    api.call("GET", "/api/meta/search-config")

    # Users
    new_user = {"email": "tour@example.local", "display_name": "Tour", "role": "viewer", "password": "long-password-1"}
    user_id = api.json("POST", "/api/users", CREATED, json=new_user)["id"]
    api.call("GET", "/api/users")
    api.call("PATCH", f"/api/users/{user_id}", json={"role": "editor"})

    # Maintainers and tags
    ann = api.json("POST", "/api/maintainers", CREATED, json={"name": "Ann Owner", "email": "ann@example.local"})
    api.call("GET", "/api/maintainers", params={"q": "ann"})
    api.call("PATCH", f"/api/maintainers/{ann['id']}", json={"name": "Ann Owner", "org_unit": "Finance IT"})
    spare = api.json("POST", "/api/maintainers", CREATED, json={"name": "Spare Team", "kind": "team"})
    tag = api.json("POST", "/api/tags", CREATED, json={"name": "invoices"})
    api.call("GET", "/api/tags", params={"category": "general"})
    api.call("PATCH", f"/api/tags/{tag['id']}", json={"name": "invoicing"})
    obsolete = api.json("POST", "/api/tags", CREATED, json={"name": "obsolete"})

    # Apps
    belegfix = {
        "name": "Belegfix",
        "short_description": "Incoming invoices",
        "homepage_url": "https://belegfix.example.com",
        "tags": ["invoicing"],
        "domains": ["finance"],
        "maintainers": [{"id": ann["id"], "role": "owner"}],
        "capabilities": [{"text": "OCR extraction of invoice data", "details": "PDF and XRechnung"}],
    }
    api.call("POST", "/api/apps", CREATED, json=belegfix)
    ledger = {"name": "Ledger", "short_description": "Bookkeeping", "capabilities": [{"text": "Post booking batches"}]}
    api.call("POST", "/api/apps", CREATED, json=ledger)
    api.call("PUT", "/api/apps/belegfix", json={**belegfix, "description": "Captures and routes invoices."})
    assert api.json("GET", "/api/apps", params={"q": "invoice"})["total"] == 1
    api.call("GET", "/api/apps/facets")
    api.call("GET", "/api/apps/belegfix")

    # Interfaces, external systems, landscape
    iface = api.json(
        "POST",
        "/api/interfaces",
        CREATED,
        json={"from": {"app": "belegfix"}, "to": {"app": "ledger"}, "name": "Bookings", "type": "file_transfer"},
    )
    api.call(
        "POST",
        "/api/interfaces",
        CREATED,
        json={"from": {"app": "ledger"}, "to": {"system": "SAP"}, "name": "GL export"},
    )
    api.call("GET", "/api/interfaces", params={"app": "belegfix"})
    api.call("GET", f"/api/interfaces/{iface['id']}")
    change_iface = {"from": {"app": "belegfix"}, "to": {"app": "ledger"}, "name": "Bookings", "status": "planned"}
    api.call("PUT", f"/api/interfaces/{iface['id']}", json=change_iface)
    datev = api.json("POST", "/api/external-systems", CREATED, json={"name": "DATEV", "vendor": "DATEV eG"})
    api.call("PUT", f"/api/external-systems/{datev['id']}", json={"name": "DATEV", "url": "https://www.datev.de"})
    api.call("GET", "/api/external-systems")
    assert {e["name"] for e in api.json("GET", "/api/landscape")["edges"]} == {"Bookings", "GL export"}

    # Search, once everything is indexed
    run_worker()
    api.call("GET", "/api/apps/belegfix/similar")
    api.call("POST", "/api/search/parse", json={"text": "- OCR for invoices\n- Booking export"})
    result = api.json("POST", "/api/search", json={"text": "- OCR extraction of invoice data\n- Post booking batches"})
    assert result["results"][0]["app"]["slug"] in {"belegfix", "ledger"}
    api.call("POST", f"/api/search/{result['search_log_id']}/feedback", NO_CONTENT, json={"rating": "up"})

    # Import and export
    api.call("GET", "/api/import/template.csv")
    api.call("GET", "/api/import/interfaces-template.csv")
    api.call("GET", "/api/import/schema.json")
    exported = api.json("GET", "/api/export")
    api.call("GET", "/api/export", params={"format": "csv"})
    api.call("GET", "/api/export", params={"format": "csv", "kind": "interfaces"})
    upload = {"file": ("catalog.json", json.dumps(exported).encode())}
    report = api.json("POST", "/api/import", params={"dry_run": "true"}, files=upload)
    assert (report["stats"]["created"], report["stats"]["updated"]) == (0, 0)  # the export imports back unchanged

    # Admin
    api.call("GET", "/api/admin/embeddings/status")
    api.call("POST", "/api/admin/embeddings/reindex", json={"scope": "stale"})
    api.call("GET", "/api/admin/search-logs", params={"only_feedback": "true"})
    api.call("GET", "/api/admin/import-runs")

    # Deletes
    api.call("DELETE", f"/api/interfaces/{iface['id']}", NO_CONTENT)
    api.call("DELETE", f"/api/external-systems/{datev['id']}", NO_CONTENT)
    api.call("DELETE", f"/api/tags/{obsolete['id']}", NO_CONTENT)
    api.call("DELETE", f"/api/maintainers/{spare['id']}", NO_CONTENT)
    api.call("DELETE", "/api/apps/ledger", NO_CONTENT)

    every = {result.ok().label for result in schema.get_all_operations()}
    assert every - api.covered == set(), "operations the tour does not cover"

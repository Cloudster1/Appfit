from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from appfit.models import Role

from .helpers import HTTP_OK, app_payload, create_app

Auth = Callable[[Role], dict[str, str]]
PUBLIC_PATHS = {"/api/health", "/api/health/ready", "/api/auth/login", "/api/auth/logout"}
UNAUTHORIZED, FORBIDDEN = 401, 403

# Minimum role per (method, path). Every API route must be listed, see test_every_route_is_covered.
MIN_ROLE: dict[tuple[str, str], Role] = {
    ("GET", "/api/auth/me"): Role.viewer,
    ("POST", "/api/auth/change-password"): Role.viewer,
    ("GET", "/api/users"): Role.admin,
    ("POST", "/api/users"): Role.admin,
    ("PATCH", "/api/users/{user_id}"): Role.admin,
    ("GET", "/api/apps"): Role.viewer,
    ("GET", "/api/apps/facets"): Role.viewer,
    ("GET", "/api/apps/{slug}"): Role.viewer,
    ("POST", "/api/apps"): Role.editor,
    ("PUT", "/api/apps/{slug}"): Role.editor,
    ("DELETE", "/api/apps/{slug}"): Role.admin,
    ("GET", "/api/apps/{slug}/similar"): Role.viewer,
    ("GET", "/api/interfaces"): Role.viewer,
    ("GET", "/api/interfaces/{interface_id}"): Role.viewer,
    ("POST", "/api/interfaces"): Role.editor,
    ("PUT", "/api/interfaces/{interface_id}"): Role.editor,
    ("DELETE", "/api/interfaces/{interface_id}"): Role.editor,
    ("GET", "/api/external-systems"): Role.viewer,
    ("POST", "/api/external-systems"): Role.editor,
    ("PUT", "/api/external-systems/{system_id}"): Role.editor,
    ("DELETE", "/api/external-systems/{system_id}"): Role.admin,
    ("GET", "/api/landscape"): Role.viewer,
    ("GET", "/api/tags"): Role.viewer,
    ("POST", "/api/tags"): Role.editor,
    ("PATCH", "/api/tags/{tag_id}"): Role.editor,
    ("DELETE", "/api/tags/{tag_id}"): Role.editor,
    ("GET", "/api/maintainers"): Role.viewer,
    ("POST", "/api/maintainers"): Role.editor,
    ("PATCH", "/api/maintainers/{maintainer_id}"): Role.editor,
    ("DELETE", "/api/maintainers/{maintainer_id}"): Role.editor,
    ("POST", "/api/search/parse"): Role.viewer,
    ("POST", "/api/search"): Role.viewer,
    ("POST", "/api/search/{log_id}/feedback"): Role.viewer,
    ("POST", "/api/import"): Role.editor,
    ("GET", "/api/import/template.csv"): Role.viewer,
    ("GET", "/api/import/schema.json"): Role.viewer,
    ("GET", "/api/import/interfaces-template.csv"): Role.viewer,
    ("GET", "/api/export"): Role.editor,
    ("GET", "/api/admin/embeddings/status"): Role.admin,
    ("POST", "/api/admin/embeddings/reindex"): Role.admin,
    ("GET", "/api/admin/search-logs"): Role.admin,
    ("GET", "/api/admin/import-runs"): Role.admin,
    ("GET", "/api/meta/enums"): Role.viewer,
    ("GET", "/api/meta/search-config"): Role.viewer,
}
DUMMY_ID = "00000000-0000-0000-0000-000000000000"


def api_routes(app: FastAPI) -> set[tuple[str, str]]:
    return {(method.upper(), path) for path, ops in app.openapi()["paths"].items() for method in ops} - {
        (m, p) for m in ("GET", "POST") for p in PUBLIC_PATHS
    }


def test_every_route_is_covered(app: FastAPI) -> None:
    assert api_routes(app) == set(MIN_ROLE)


def concrete(path: str) -> str:
    return (
        path.replace("{slug}", "no-such-app")
        .replace("{user_id}", DUMMY_ID)
        .replace("{tag_id}", DUMMY_ID)
        .replace("{maintainer_id}", DUMMY_ID)
        .replace("{log_id}", DUMMY_ID)
    )


@pytest.mark.parametrize(("method", "path"), sorted(MIN_ROLE))
def test_role_matrix(client: TestClient, auth: Auth, method: str, path: str) -> None:
    url = concrete(path)
    assert client.request(method, url).status_code == UNAUTHORIZED
    required = MIN_ROLE[(method, path)]
    for role in Role:
        status = client.request(method, url, headers=auth(role), json={}).status_code
        if role.rank < required.rank:
            assert status == FORBIDDEN, (role, status)
        else:
            assert status not in (UNAUTHORIZED, FORBIDDEN), (role, status)


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "database": True, "model_loaded": False, "detail": None}
    ready = client.get("/api/health/ready")
    assert ready.status_code == HTTP_OK and ready.json()["model_loaded"] is True


def test_embedding_status_and_reindex(client: TestClient, auth: Auth, run_worker: Callable[[], int]) -> None:
    admin = auth(Role.admin)
    create_app(client, auth(Role.editor), app_payload("Indexed", ["one", "two"]))
    status = client.get("/api/admin/embeddings/status", headers=admin).json()
    assert status["pending"] == 3 and status["model_id"] == "fake-hash-v1"
    run_worker()
    assert client.get("/api/admin/embeddings/status", headers=admin).json()["pending"] == 0
    after = client.post("/api/admin/embeddings/reindex", json={"scope": "all"}, headers=admin).json()
    assert after["pending"] == 3
    assert run_worker() == 3


def test_meta(client: TestClient, auth: Auth) -> None:
    v = auth(Role.viewer)
    assert "retired" in client.get("/api/meta/enums", headers=v).json()["lifecycle_status"]
    cfg = client.get("/api/meta/search-config", headers=v).json()
    assert cfg["model_id"] == "fake-hash-v1"
    assert cfg["thresholds"]["covered"] > cfg["thresholds"]["partial"]

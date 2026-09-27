"""Edge cases found by fuzzing the API against its OpenAPI spec (tests/contract)."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from appfit.config import MAX_PAGE
from appfit.models import Role

from .helpers import app_payload, create_app

Auth = Callable[[Role], dict[str, str]]
HTTP_OK, HTTP_BAD_REQUEST, HTTP_METHOD_NOT_ALLOWED, HTTP_UNPROCESSABLE = 200, 400, 405, 422
JSON = {"Content-Type": "application/json"}


def _unstorable_at(resp) -> list:  # type: ignore[no-untyped-def,type-arg]
    assert resp.status_code == HTTP_UNPROCESSABLE, resp.text
    return [e["loc"] for e in resp.json()["detail"] if e["type"] == "string_unstorable"]


def test_text_postgres_cannot_store_is_rejected_not_a_crash(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    assert _unstorable_at(client.post("/api/tags", json={"name": "a\x00b"}, headers=ed)) == [["body", "name"]]
    assert _unstorable_at(client.get("/api/apps", params={"q": "\x00"}, headers=ed)) == [["query", "q"]]
    assert _unstorable_at(client.get("/api/apps/a%00b", headers=ed)) == [["path"]]
    lone_surrogate = b'{"name": "\\ud800"}'
    resp = client.post("/api/tags", content=lone_surrogate, headers={**ed, **JSON})
    assert _unstorable_at(resp) == [["body", "name"]]
    assert client.post("/api/search", json={"text": "\x00"}, headers=ed).status_code == HTTP_UNPROCESSABLE


def test_imports_reject_nul_characters(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    for name, content in (("a.csv", b"name\nA\x00B\n"), ("a.json", b'[{"name": "A\\u0000B"}]')):
        resp = client.post("/api/import", files={"file": (name, content)}, headers=ed)
        assert resp.status_code == HTTP_BAD_REQUEST, resp.text
        assert "NUL" in resp.json()["detail"]


def test_page_numbers_are_bounded(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.admin)
    for path in ("/api/apps", "/api/admin/search-logs"):
        assert client.get(path, params={"page": MAX_PAGE}, headers=ed).status_code == HTTP_OK
        assert client.get(path, params={"page": 10**18}, headers=ed).status_code == HTTP_UNPROCESSABLE


def test_405_lists_every_method_of_the_path(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    for path, allowed in (("/api/apps", "GET, POST"), ("/api/apps/x", "DELETE, GET, PUT"), ("/api/apps/facets", "GET")):
        resp = client.request("PATCH", path, headers=ed)
        assert resp.status_code == HTTP_METHOD_NOT_ALLOWED, (path, resp.text)
        assert resp.headers["allow"] == allowed


def test_route_words_are_reserved_slugs(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    assert create_app(client, ed, app_payload("Facets"))["slug"] == "facets-2"
    resp = client.post("/api/apps", json=app_payload("Facet board", slug="facets"), headers=ed)
    assert resp.status_code == HTTP_UNPROCESSABLE


def test_blank_names_are_rejected(client: TestClient, auth: Auth) -> None:
    ed = auth(Role.editor)
    for body in ({"name": "   "}, {"name": "\x1f"}):
        assert client.post("/api/tags", json=body, headers=ed).status_code == HTTP_UNPROCESSABLE
    user = {"email": "x@example.local", "display_name": "　", "password": "long-enough-password"}
    assert client.post("/api/users", json=user, headers=auth(Role.admin)).status_code == HTTP_UNPROCESSABLE

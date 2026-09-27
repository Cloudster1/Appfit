from collections.abc import Callable

from fastapi.testclient import TestClient

from appfit.models import Role, User
from tests.conftest import TEST_PASSWORD

from .helpers import HTTP_CREATED, HTTP_NO_CONTENT, HTTP_OK


def test_login_sets_httponly_cookie_and_me_works(client: TestClient, users: dict[Role, User]) -> None:
    user = users[Role.editor]
    resp = client.post("/api/auth/login", json={"email": user.email.upper(), "password": TEST_PASSWORD})
    assert resp.status_code == HTTP_OK
    cookie = resp.headers["set-cookie"]
    assert "appfit_session=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    me = client.get("/api/auth/me")
    assert me.status_code == HTTP_OK
    assert me.json()["role"] == "editor"
    assert client.post("/api/auth/logout").status_code == HTTP_NO_CONTENT
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_and_inactive_user(client: TestClient, users: dict[Role, User], db) -> None:  # type: ignore[no-untyped-def]
    user = users[Role.viewer]
    assert client.post("/api/auth/login", json={"email": user.email, "password": "nope"}).status_code == 401
    user.is_active = False
    db.commit()
    resp = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert resp.status_code == 401


def test_csrf_header_required_for_cookie_writes(app, users: dict[Role, User]) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as bare:
        resp = bare.post("/api/auth/login", json={"email": users[Role.viewer].email, "password": TEST_PASSWORD})
        assert resp.status_code == 403
        assert "X-Requested-With" in resp.json()["detail"]


def test_deactivated_user_token_is_rejected(
    client: TestClient,
    users: dict[Role, User],
    auth: Callable[[Role], dict[str, str]],
    db,  # type: ignore[no-untyped-def]
) -> None:
    headers = auth(Role.viewer)
    assert client.get("/api/auth/me", headers=headers).status_code == HTTP_OK
    users[Role.viewer].is_active = False
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_change_password(client: TestClient, users: dict[Role, User], auth: Callable[[Role], dict[str, str]]) -> None:
    h = auth(Role.viewer)
    bad = client.post(
        "/api/auth/change-password", json={"current_password": "x", "new_password": "a-new-password"}, headers=h
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "a-new-password"},
        headers=h,
    )
    assert ok.status_code == HTTP_NO_CONTENT
    login = client.post("/api/auth/login", json={"email": users[Role.viewer].email, "password": "a-new-password"})
    assert login.status_code == HTTP_OK


def test_user_admin_flow(client: TestClient, users: dict[Role, User], auth: Callable[[Role], dict[str, str]]) -> None:
    admin = auth(Role.admin)
    body = {"email": "New.User@Corp.Local", "display_name": "New User", "role": "editor", "password": "long-password"}
    resp = client.post("/api/users", json=body, headers=admin)
    assert resp.status_code == HTTP_CREATED
    created = resp.json()
    assert created["email"] == "new.user@corp.local"
    assert client.post("/api/users", json=body, headers=admin).status_code == 409
    patched = client.patch(f"/api/users/{created['id']}", json={"role": "viewer", "is_active": False}, headers=admin)
    assert patched.json()["role"] == "viewer" and patched.json()["is_active"] is False
    me_id = str(users[Role.admin].id)
    assert client.patch(f"/api/users/{me_id}", json={"role": "viewer"}, headers=admin).status_code == 400
    assert len(client.get("/api/users", headers=admin).json()) >= 4

"""OpenAPI document details FastAPI cannot infer: auth, roles, error responses and operation ids."""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from starlette.routing import compile_path

from appfit.api.deps import get_embedder
from appfit.auth.deps import get_current_user, require_admin, require_editor, require_viewer
from appfit.config import Settings
from appfit.models import Role
from appfit.schemas.common import ErrorOut

CSRF_HEADER_NAME = "X-Requested-With"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SECURITY: list[dict[str, list[str]]] = [{"cookieAuth": []}, {"bearerAuth": []}]
ERROR_REF = {"$ref": "#/components/schemas/ErrorOut"}
ROLE_DEPENDENCIES = {require_viewer: Role.viewer, require_editor: Role.editor, require_admin: Role.admin}

ERROR_DESCRIPTIONS = {
    HTTPStatus.BAD_REQUEST: "The body could not be parsed, or the request breaks a rule; `detail` says which.",
    HTTPStatus.UNAUTHORIZED: "Not signed in, or the session or token has expired.",
    HTTPStatus.FORBIDDEN: f"The role is too low, or a cookie-authenticated write lacks the {CSRF_HEADER_NAME} header.",
    HTTPStatus.NOT_FOUND: "No such resource.",
    HTTPStatus.CONFLICT: "Conflicts with existing data; `detail` says what.",
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: "The upload exceeds the configured size limit.",
    HTTPStatus.SERVICE_UNAVAILABLE: "The embedding model is still loading or failed to load.",
}

TAGS = [
    {"name": "auth", "description": "Sign in and out, the current user and password changes."},
    {"name": "apps", "description": "The application catalog: apps with capabilities, tags and maintainers."},
    {"name": "interfaces", "description": "Interfaces between apps and external systems, and the landscape graph."},
    {"name": "search", "description": "Explainable matching of requirements against the catalog."},
    {"name": "import", "description": "CSV and JSON import, export and templates."},
    {"name": "tags", "description": "Tags, tech stack and domains shared by apps."},
    {"name": "maintainers", "description": "People and teams that own or maintain apps."},
    {"name": "users", "description": "User accounts and roles (admin only)."},
    {"name": "admin", "description": "Embedding index status, reindexing and logs (admin only)."},
    {"name": "meta", "description": "Enum values and search settings for clients."},
    {"name": "health", "description": "Liveness and readiness probes."},
]

DESCRIPTION = f"""Appfit is an application catalog with explainable matching of requirements to apps.

**Authentication.** `POST /api/auth/login` sets an HttpOnly session cookie and also returns the same token
for use as `Authorization: Bearer <token>`.
Cookie-authenticated writes (POST, PUT, PATCH, DELETE) must send the `{CSRF_HEADER_NAME}` header,
bearer clients need not.

**Roles.** `viewer` < `editor` < `admin`; each operation names its minimum role in `x-required-role`.

**Errors.** Error bodies are `{{"detail": "..."}}`; request validation errors (422) list the offending fields.
Text anywhere in a request (path, query, JSON body) must not contain NUL characters or lone UTF-16 surrogates,
which the database cannot store; such requests get 422.
"""


def operation_id(route: APIRoute) -> str:
    """Operation ids are the route function names, which are unique across the API."""
    return route.name


def _dependencies(dependant: Dependant) -> Iterator[Any]:
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependencies(dep)


def _error(code: HTTPStatus) -> dict[str, Any]:
    return {"model": ErrorOut, "description": ERROR_DESCRIPTIONS[code]}


def errors(*codes: HTTPStatus) -> dict[int | str, dict[str, Any]]:
    """Route-specific error responses, for the `responses` argument of a route decorator."""
    return {int(code): _error(code) for code in codes}


@dataclass(frozen=True)
class ApiRoute:
    path: str
    route: APIRoute

    @property
    def regex(self) -> re.Pattern[str]:
        return compile_path(self.path)[0]


def api_routes(prefix: str, routers: Iterable[APIRouter]) -> list[ApiRoute]:
    return [ApiRoute(prefix + r.path, r) for router in routers for r in router.routes if isinstance(r, APIRoute)]


def allowed_methods(routes: Iterable[ApiRoute], path: str) -> list[str]:
    """Every method served at this path (Starlette lists only the first match's); literal paths win over templates."""
    matching = [r for r in routes if r.regex.match(path)]
    literal = [r for r in matching if r.path == path]
    return sorted({m for r in literal or matching for m in r.route.methods or ()})


def _document_operation(op: dict[str, Any], route: APIRoute, method: str) -> None:
    calls = set(_dependencies(route.dependant))
    role = max((r for dep, r in ROLE_DEPENDENCIES.items() if dep in calls), key=lambda r: r.rank, default=None)
    authenticated = role is not None or get_current_user in calls
    codes: set[HTTPStatus] = set()
    if authenticated:
        codes.add(HTTPStatus.UNAUTHORIZED)
    if (role is not None and role != Role.viewer) or method in UNSAFE_METHODS:
        codes.add(HTTPStatus.FORBIDDEN)
    if route.dependant.path_params:
        codes.add(HTTPStatus.NOT_FOUND)
    if route.body_field is not None:
        codes.add(HTTPStatus.BAD_REQUEST)
    if get_embedder in calls:
        codes.add(HTTPStatus.SERVICE_UNAVAILABLE)
    responses = op["responses"]
    for code in sorted(codes):
        responses.setdefault(
            str(int(code)),
            {"description": ERROR_DESCRIPTIONS[code], "content": {"application/json": {"schema": ERROR_REF}}},
        )
    op["responses"] = dict(sorted(responses.items()))
    if authenticated:
        op["security"] = SECURITY
        op["x-required-role"] = (role or Role.viewer).value


def install_openapi(app: FastAPI, settings: Settings, routes: list[ApiRoute]) -> None:
    """Add auth, roles and error responses to every operation and describe the security schemes."""

    def build() -> dict[str, Any]:
        if app.openapi_schema is None:
            doc = get_openapi(
                title=app.title, version=app.version, description=DESCRIPTION, routes=app.routes, tags=TAGS
            )
            components = doc.setdefault("components", {})
            components.setdefault("schemas", {})[ErrorOut.__name__] = ErrorOut.model_json_schema()
            components["securitySchemes"] = {
                "cookieAuth": {"type": "apiKey", "in": "cookie", "name": settings.cookie_name},
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
            }
            for r in routes:
                for method in r.route.methods or ():
                    _document_operation(doc["paths"][r.path][method.lower()], r.route, method)
            app.openapi_schema = doc
        return app.openapi_schema

    app.openapi = build  # type: ignore[method-assign]

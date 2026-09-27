from typing import Any

import pytest
from openapi_spec_validator import validate

from appfit.models import Role
from appfit.openapi_dump import DEFAULT_TARGET, render, spec

UNSAFE = {"post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    return spec()


def _operations(doc: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [(path, method, op) for path, ops in doc["paths"].items() for method, op in ops.items()]


def test_committed_spec_is_current(doc: dict[str, Any]) -> None:
    assert DEFAULT_TARGET.read_text(encoding="utf-8") == render(doc), "docs/openapi.yaml is stale: run `make gen-api`"


def test_spec_is_valid_openapi(doc: dict[str, Any]) -> None:
    validate(doc)


def test_every_operation_is_documented(doc: dict[str, Any]) -> None:
    ids = [op["operationId"] for _, _, op in _operations(doc)]
    assert len(ids) == len(set(ids))
    for path, method, op in _operations(doc):
        label = f"{method.upper()} {path}"
        assert op.get("description") and op.get("tags"), label
        codes = set(op["responses"])
        if "security" in op:
            assert "401" in codes and op["x-required-role"] in {r.value for r in Role}, label
        if method in UNSAFE:
            assert "403" in codes, label
        if "{" in path:
            assert "404" in codes, label
        for code, response in op["responses"].items():
            if code.startswith(("4", "5")) and code != "422":
                schema = response["content"]["application/json"]["schema"]
                assert schema["$ref"].endswith(("/ErrorOut", "/HealthOut")), (label, code)


def test_public_operations_are_only_health_and_sign_in(doc: dict[str, Any]) -> None:
    public = {f"{m.upper()} {p}" for p, m, op in _operations(doc) if "security" not in op}
    assert public == {"GET /api/health", "GET /api/health/ready", "POST /api/auth/login", "POST /api/auth/logout"}

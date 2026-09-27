"""Property-based tests: generated requests for every operation must get answers that match the spec."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import settings
from schemathesis.config import SchemathesisConfig

from appfit.main import CSRF_HEADER
from appfit.models import Role

Auth = Callable[[Role], dict[str, str]]
CONFIG_PATH = Path(__file__).with_name("schemathesis.toml")
# Raise for a deeper run, e.g. FUZZ_EXAMPLES=500 make test-backend.
MAX_EXAMPLES = int(os.environ.get("FUZZ_EXAMPLES", "30"))


@pytest.fixture
def api_schema(app: FastAPI, auth: Auth) -> schemathesis.BaseSchema:
    # Credentials go through the spec's bearerAuth scheme, so auth checks can swap in invalid ones.
    token = auth(Role.admin)["Authorization"].removeprefix("Bearer ")
    config = CONFIG_PATH.read_text() + f'\n[auth.openapi.bearerAuth]\nbearer = "{token}"\n'
    return schemathesis.openapi.from_asgi("/api/openapi.json", app, config=SchemathesisConfig.from_str(config))


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(max_examples=MAX_EXAMPLES, deadline=None)
def test_api_conforms_to_spec(case: schemathesis.Case) -> None:
    case.call_and_validate(headers={CSRF_HEADER: "XMLHttpRequest"})

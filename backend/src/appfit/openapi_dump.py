import json
import sys
from pathlib import Path
from typing import Any

import yaml

from appfit.config import Settings
from appfit.main import create_app

DEFAULT_TARGET = Path(__file__).resolve().parents[3] / "docs" / "openapi.yaml"
YAML_WIDTH = 120


def spec() -> dict[str, Any]:
    app = create_app(Settings(_env_file=None, embedding_backend="fake"), start_background=False)
    # A JSON round trip turns enum keys (HTTP status codes) into plain strings.
    doc: dict[str, Any] = json.loads(json.dumps(app.openapi()))
    return doc


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # Block style keeps multi-line descriptions readable.
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


_Dumper.add_representer(str, _represent_str)


def render(doc: dict[str, Any]) -> str:
    """The committed form of the spec: YAML in the order FastAPI produces, ASCII only."""
    header = "# Generated from the FastAPI app by `make gen-api`; do not edit by hand.\n"
    return header + yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=False, width=YAML_WIDTH)


def main(target: str | None = None) -> None:
    """Write the OpenAPI document; the typed frontend client is generated from it."""
    path = Path(target) if target else DEFAULT_TARGET
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(spec()), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

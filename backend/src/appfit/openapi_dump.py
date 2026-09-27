import json
import sys
from pathlib import Path

from appfit.config import Settings
from appfit.main import create_app


def main(target: str) -> None:
    """Write the OpenAPI document (used to generate the typed frontend client)."""
    app = create_app(Settings(_env_file=None, embedding_backend="fake"), start_background=False)
    Path(target).write_text(json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])

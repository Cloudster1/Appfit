# Contributing to Appfit

Thanks for helping. Bug reports, ideas and pull requests are welcome.

## Before you start

- For larger changes, open an issue first so we can agree on the approach.
- Security problems: see [SECURITY.md](SECURITY.md) and report them privately.

## Development setup

Requirements: Docker with Compose, [uv](https://docs.astral.sh/uv/) and make. Node is not required; the frontend
tooling runs in a container.

```bash
cp .env.example .env          # set JWT_SECRET (32+ random characters) and BOOTSTRAP_ADMIN_PASSWORD
make setup                    # backend venv and frontend dependencies
make dev                      # API on :8000, UI on :5173, Postgres on :5432
```

`make help` lists all commands; the [README](README.md#development) explains the layout.

## Checks

Pull requests must pass CI, which runs the same checks as:

```bash
make lint        # ruff, mypy, eslint, tsc
make test        # backend (pytest with real pgvector) and frontend (Vitest)
make helm-lint   # Helm chart
```

The backend tests include contract tests against the OpenAPI spec, so API changes need `make gen-api`, which
updates `docs/openapi.yaml` and the frontend types; commit both. Changes to matching or embeddings should keep
`make eval` from regressing (see "Evaluation and calibration" in the README).

## Screenshots

The README screenshots come from `frontend/e2e/screenshots.spec.ts`. To refresh them, run it against a running,
seeded stack (`make up && make seed`):

```bash
docker run --rm --network host -v "$PWD/frontend":/app -v "$PWD/docs/screenshots":/shots \
  -v appfit-fe-nm:/app/node_modules -w /app -e SCREENSHOTS_DIR=/shots \
  -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD mcr.microsoft.com/playwright:v1.63.0-noble \
  npx playwright test e2e/screenshots.spec.ts
```

## Conventions

- Source files are ASCII only.
- Docstrings are at most two lines; say what a function is for, not how.
- No magic numbers: tunable values live in `backend/src/appfit/config.py` and `frontend/src/config.ts`.
- New behavior comes with tests; bug fixes with a test that fails without the fix.
- Commit messages: a short summary line, then what changed and why.

## Releases

Maintainers release by updating the version in `backend/pyproject.toml`, `backend/src/appfit/__init__.py`,
`frontend/package.json` and `deploy/helm/appfit/Chart.yaml`, adding a section to `CHANGELOG.md`, and pushing a tag
`vX.Y.Z`. The release workflow checks that the versions match, publishes the images and the Helm chart to GHCR and
creates the GitHub release.

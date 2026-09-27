# Appfit developer commands. Backend tools run from a venv outside /mnt (fast on WSL);
# frontend tools run in a node container, so no local Node install is needed.
SHELL := /bin/bash
COMPOSE := docker compose -f compose.yaml
COMPOSE_DEV := docker compose -f compose.yaml -f compose.dev.yaml
export UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/appfit
VENV_BIN := $(UV_PROJECT_ENVIRONMENT)/bin
DB_URL ?= postgresql+psycopg://appfit:appfit@localhost:5432/appfit
TEST_DB_URL ?= postgresql+psycopg://appfit:appfit@localhost:5432/appfit_test
PNPM = docker run --rm -v "$(CURDIR)/frontend":/app -v appfit-fe-nm:/app/node_modules \
	-v appfit-corepack:/root/.cache/node/corepack -w /app node:22-alpine sh -c 'corepack enable >/dev/null 2>&1 && pnpm $(1)'

.PHONY: help setup up down dev db migrate seed test test-backend test-frontend test-model test-db eval eval-sweep \
	lint format gen-api build logs e2e selfcheck helm-lint helm-kind

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Create the backend venv (Python 3.12, with ML extras) and install frontend deps
	cd backend && uv sync --extra ml
	$(call PNPM,install --frozen-lockfile)

up: ## Build and start the production-like stack on http://localhost:8080
	$(COMPOSE) up -d --build

down: ## Stop all containers
	$(COMPOSE_DEV) down

dev: ## Start the dev stack with hot reload (API :8000, web :5173, db :5432)
	$(COMPOSE_DEV) up --build

db: ## Start only Postgres (for local backend development and tests)
	$(COMPOSE_DEV) up -d db

logs: ## Follow backend logs
	$(COMPOSE) logs -f backend

migrate: ## Apply database migrations (local venv)
	cd backend && DATABASE_URL=$(DB_URL) $(VENV_BIN)/alembic upgrade head

seed: ## Load the demo catalog (45 apps) into the database
	cd backend && DATABASE_URL=$(DB_URL) $(VENV_BIN)/appfit seed eval/seed_apps.json

test-db: db
	@$(COMPOSE) exec -T db psql -U appfit -tc "SELECT 1 FROM pg_database WHERE datname='appfit_test'" | grep -q 1 \
		|| $(COMPOSE) exec -T db psql -U appfit -c "CREATE DATABASE appfit_test"

test: selfcheck test-backend test-frontend ## Run all fast tests

selfcheck: ## Check that the frontend command macro expands (a ':=' definition once dropped all pnpm args)
	@$(MAKE) -s -n test-frontend lint | grep -q "pnpm test" \
		&& $(MAKE) -s -n lint | grep -q "pnpm exec tsc --noEmit" \
		|| { echo "Makefile PNPM macro does not pass its arguments; define it with '=' not ':='"; exit 1; }

test-backend: test-db ## Backend unit + integration tests (fake embedder, real pgvector)
	cd backend && TEST_DATABASE_URL=$(TEST_DB_URL) $(VENV_BIN)/pytest

test-model: ## Opt-in tests with the real embedding model
	cd backend && $(VENV_BIN)/pytest -m model

test-frontend: ## Frontend unit tests (Vitest)
	$(call PNPM,test)

eval: ## Retrieval metrics with the real model on the seeded catalog
	cd backend && DATABASE_URL=$(DB_URL) $(VENV_BIN)/appfit eval --report eval/reports/latest.json > /dev/null
	@echo "Report: backend/eval/reports/latest.json"

eval-sweep: ## Like eval, plus suggested thresholds for thresholds.yaml
	cd backend && DATABASE_URL=$(DB_URL) $(VENV_BIN)/appfit eval --sweep --report eval/reports/latest.json > /dev/null
	@echo "Report: backend/eval/reports/latest.json"

lint: ## Ruff, mypy, eslint and tsc
	cd backend && $(VENV_BIN)/ruff check src tests alembic && $(VENV_BIN)/ruff format --check src tests alembic \
		&& $(VENV_BIN)/mypy src
	$(call PNPM,lint) && $(call PNPM,exec tsc --noEmit)

format: ## Auto-format backend and frontend
	cd backend && $(VENV_BIN)/ruff check --fix src tests alembic && $(VENV_BIN)/ruff format src tests alembic
	$(call PNPM,format)

gen-api: ## Regenerate docs/openapi.yaml and the typed frontend API client from it
	cd backend && $(VENV_BIN)/python -m appfit.openapi_dump ../docs/openapi.yaml
	docker run --rm -v "$(CURDIR)/frontend":/app -v "$(CURDIR)/docs":/docs:ro -v appfit-fe-nm:/app/node_modules \
		-v appfit-corepack:/root/.cache/node/corepack -w /app node:22-alpine \
		sh -c 'corepack enable >/dev/null 2>&1 && pnpm gen:api'

build: ## Production frontend build
	$(call PNPM,build)

e2e: ## Playwright smoke tests against the running stack (make up && make seed first)
	docker run --rm --network host -v "$(CURDIR)/frontend":/app -v appfit-fe-nm:/app/node_modules -w /app \
		-e E2E_BASE_URL=$${E2E_BASE_URL:-http://localhost:8080} -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD \
		mcr.microsoft.com/playwright:v1.63.0-noble sh -c 'npx playwright test'

HELM_CHART = deploy/helm/appfit

helm-lint: ## Lint the Helm chart and validate its manifests for every example values file (needs helm, kubeconform)
	helm lint $(HELM_CHART)
	@for values in "" $(wildcard $(HELM_CHART)/ci/*-values.yaml); do \
		echo "== $${values:-default values}"; \
		helm lint $(HELM_CHART) $${values:+-f $$values} --quiet \
		&& helm template appfit $(HELM_CHART) $${values:+-f $$values} | kubeconform -strict -summary - || exit 1; \
	done

helm-kind: ## Install the chart into a local kind cluster and run helm test (needs kind, kubectl, helm)
	deploy/helm/kind-smoke.sh

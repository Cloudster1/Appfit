# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-27

First release.

### Catalog
- Apps with capabilities, requirements and features, tags, tech stack, domains, maintainers, license and lifecycle.
- Catalog and search on one page with facets for lifecycle, domain and license type; tile and matrix views.
- CSV and JSON import (dry run, partial updates, German column names) and export, with templates.
- Local users with the roles viewer, editor and admin.

### Matching
- Requirements in German or English, as free text or a list with priorities (must, should, could).
- Hybrid retrieval: pgvector HNSW over local `BAAI/bge-m3` embeddings plus PostgreSQL full-text search, fused with RRF.
- Explained results: which capability covers which requirement, gaps, a clear "no match" answer, and a CSV export
  of the requirement x app matrix.
- Evaluation harness (`make eval`) with a labelled query set and calibrated thresholds.

### Interfaces
- Interfaces between apps and external systems (type, data objects, frequency, status, direction).
- Landscape graph, app neighbourhood, connections in search results, and interfaces as matching evidence.

### API
- OpenAPI 3.1 spec in `docs/openapi.yaml` with auth, roles and every error response; Swagger UI at `/api/docs`.
- Contract tests: a tour of every operation and Schemathesis fuzzing against the spec.

### Deployment
- Docker Compose setup and a Helm chart (`deploy/helm/appfit`) with optional PostgreSQL + pgvector, a separate
  embedding worker, generated secrets, a model cache volume and ingress. The pods meet the "restricted" Pod Security
  Standard.
- Images and the chart are published to GHCR on each release.

[Unreleased]: ../../compare/v0.1.0...HEAD
[0.1.0]: ../../releases/tag/v0.1.0

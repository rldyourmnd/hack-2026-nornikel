<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: a81edd1 Merge pull request #14 from rldyourmnd/perf/table-row-cap
Scope: Makefile; .github/workflows/ci.yml; docker-compose.yml; docker-compose.server.yml; services/api/Dockerfile; apps/web/nginx.conf; docs/deployment/nornikel-nddev.md; docs/deployment/full-ingest-runbook.md; scripts/ingest_corpus.py; scripts/run_realcase_eval.py
Area: RELEASE
-->

# RELEASE-01-VALIDATION

## Purpose

Capture validation, deployment, compose, and batch-ingest rollout contracts.

## Source Of Truth

- `Makefile`: local validation and dev commands.
- `.github/workflows/ci.yml`: PR/main CI.
- `.github/workflows/deploy.yml`: auto-deploy on push to `main`.
- `docker-compose.yml` / `docker-compose.server.yml`: local/server topology.
- `services/api/Dockerfile`: API image dependencies.
- `apps/web/nginx.conf`: web proxy limits/timeouts.
- `docs/deployment/full-ingest-runbook.md`: current DATA_HACK ingest/swap runbook.
- `scripts/ingest_corpus.py`: direct batch ingest command.

## Entry Points

- `make ci`: full local/CI-quality gate.
- `make eval-realcase`: live API real-corpus honesty check.
- `docker compose config`: compose syntax validation.
- `scripts/ingest_corpus.py --dir DATA_HACK --sample N --workers N --max-mb N`: batch ingest.
- `scripts/reindex.py`: rebuild current configured Qdrant collections from DuckDB.

## Current Behavior

- Pushes to `main` auto-deploy through GitHub Actions.
- The live working provider profile is dataeyes + OpenAI-compatible embeddings. `docs/deployment/full-ingest-runbook.md` documents zero-downtime builds into separate `DUCKDB_PATH` and Qdrant collections, then an atomic swap.
- The no-GPU production path uses pypdfium2 PDF text extraction, remote dense embeddings, and optional Docling workers only for formats still handled by Docling.
- `qdrant/qdrant:v1.16.3` is pinned in compose. The Python client is currently 1.18.0 and emits a compatibility warning against server 1.16.3.
- `make eval` no longer exists; use `make eval-realcase`.

## Contracts And Data

- `MAX_SOURCE_UPLOAD_BYTES` must stay at or below active Nginx `client_max_body_size`.
- The API process holds one persistent DuckDB connection; direct file access batch tools need a separate DB path or an API-stop window.
- Runtime secrets stay server-side in `.env`, never in git.
- For zero-downtime graph builds, use separate `DUCKDB_PATH`, `QDRANT_COLLECTION`, and `QDRANT_ENTITY_COLLECTION`.

## Verification

- `uv run ruff check .`
- `uv run mypy`
- `uv run pytest`
- `cd apps/web && npm run typecheck`
- `cd apps/web && npm run build`
- `docker compose config`

<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: 1db4c68 docs(instructions): note sharded ingest workflow
Scope: Makefile; .github/workflows/ci.yml; docker-compose.yml; docker-compose.server.yml; services/api/Dockerfile; apps/web/nginx.conf; docs/deployment/nornikel-nddev.md; docs/deployment/full-ingest-runbook.md; scripts/ingest_corpus.py; scripts/merge_duckdb_shards.py; scripts/run_realcase_eval.py
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
- `docs/deployment/full-ingest-runbook.md`: DATA_HACK ingest/swap runbook.
- `scripts/ingest_corpus.py`: direct batch ingest command.
- `scripts/merge_duckdb_shards.py`: merge independently built shard ledgers.

## Entry Points

- `make ci`: full local/CI-quality gate.
- `make eval-realcase`: live API real-corpus honesty check.
- `docker compose config`: compose syntax validation.
- `scripts/ingest_corpus.py --dir DATA_HACK --sample N --workers N --max-mb N`: batch ingest.
- `scripts/ingest_corpus.py --shard-count N --shard-index I`: deterministic
  shard slice of the selected corpus list.
- `scripts/merge_duckdb_shards.py --output data/catalog_full.duckdb data/catalog_full_shard_*.duckdb`: merge shard ledgers before swap.
- `scripts/reindex.py`: rebuild configured Qdrant collections from DuckDB.

## Current Behavior

- Pushes to `main` auto-deploy through GitHub Actions.
- Deploy cleans stale top-level code files before extracting the tracked tree, preserving `.env*`, `data/`, `DATA_HACK/`, and `ingest_*.log`.
- The production profile is provider-neutral in git: runtime `.env` supplies the OpenAI-compatible LLM and embedding endpoints.
- DataEyes/OpenAI-compatible GPT-5-family models use
  `LLM_REASONING_EFFORT=low`; the LiteLLM gateway sets `temperature=1` for
  `gpt-5*` model IDs because those chat completions reject `temperature=0`.
  Do not set output token caps for extraction/answer JSON because truncated
  structured output fails validation.
- Yandex AI Studio runtime configuration is env-only: `LLM_API_BASE`,
  `LLM_API_KEY`, `LLM_EXTRACTION_MODEL`, `LLM_ANSWER_MODEL`,
  `YANDEX_FOLDER_ID`, `EMBEDDING_BACKEND=yandex`, `YANDEX_API_KEY`,
  `YANDEX_EMBED_DOC_MODEL`, `YANDEX_EMBED_QUERY_MODEL`, and
  `YANDEX_EMBED_DIM`. Do not store account keys or folder-specific secrets in git.
- Zero-downtime graph builds use separate `DUCKDB_PATH`, `QDRANT_COLLECTION`, and `QDRANT_ENTITY_COLLECTION`, then an atomic swap.
- High-throughput builds should shard writes across several independent
  DuckDB files and merge them: one process per shard avoids the single-file
  writer bottleneck while all shards can write to the same fresh Qdrant
  collection. The runbook's validated 40-file benchmark improved from 1439s
  on the previous single-process DataEyes/MiniMax profile to 790s with
  single-process `gpt-5.4-mini`/`text-embedding-3-small`, and then to a 500s
  max-shard wall clock with 4 shards. All three completed 40/40 with 0 failed
  files. The merged 4-shard ledger was verified at 40 sources, 16,102 evidence
  spans, 1,067 entities, 23,672 numeric facts, and the shared Qdrant collection
  held 16,102 points.
- The no-GPU production path uses pypdfium2 PDF text extraction, remote dense embeddings when configured, and Docling only where still needed.
- `qdrant/qdrant:v1.16.3` is pinned in compose.
- `make eval` no longer exists; use `make eval-realcase`.

## Contracts

- `MAX_SOURCE_UPLOAD_BYTES` must stay at or below active Nginx `client_max_body_size`.
- The API process holds one persistent DuckDB connection; direct file access batch tools need a separate DB path or an API-stop window.
- Runtime secrets stay server-side in `.env`, never in git.
- Use a new Qdrant collection when vector dimension or embedding backend changes.
- For `text-embedding-3-small`, use a fresh 1536-dim Qdrant collection.
  Live DataEyes probing showed `EMBEDDING_BATCH=256` and `EMBEDDING_RPS=32`
  as a stable production profile; larger concurrent embedding batches produced
  long-tail read timeouts.
- Yandex v2 embeddings default to 768 dimensions in this repo; switching
  between 256/512/768 or between Yandex/OpenAI/local embeddings requires a fresh
  Qdrant collection and reindex.

## Verification

- `uv run ruff check .`
- `uv run mypy`
- `uv run pytest`
- `cd apps/web && npm run typecheck`
- `cd apps/web && npm run build`
- `docker compose config`

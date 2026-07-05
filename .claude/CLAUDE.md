# Project Notes

## Scope

Repository: `hack-2026-nornikel`.

Product: evidence-led QA and knowledge graph over a Russian
mining-and-metallurgy R&D corpus.

## Architecture

- Backend sources: `src/nornikel_kg/`.
- FastAPI routes: `services/api/routes/`.
- Frontend: `apps/web/`.
- Deployment docs: `docs/deployment/`.
- Durable maintainer memory: `.serena/memories/`.

Layering:

- Domain and services depend on ports.
- Vendor clients live in adapters.
- DuckDB is authoritative; Qdrant is retrieval-only.
- Only `src/nornikel_kg/adapters/llm/gateway.py` imports LiteLLM.
- Production ingest must not require local GPU or graphical-system resources.

## Runtime Profile

- Provider and model IDs are runtime configuration, not hardcoded domain facts.
- LLM calls go through the LiteLLM gateway.
- Dense embeddings can be remote (`EMBEDDING_BACKEND=openai`) or local/fake for
  development and tests.
- PDF ingest defaults to `PDF_PARSE_MODE=pypdfium`; Docling remains available for
  supported office formats and optional PDF fallback.
- Source visibility is bounded by `JURY_ALLOWED_LABELS`; request labels may only
  narrow that floor.

## Commands

```bash
uv run ruff check .
uv run mypy
uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
make ci
make eval-realcase
docker compose config
```

`make eval-realcase` requires a running API.

## Deployment

- Current deployment repo: this repository.
- The pre-migration archive repository is frozen; do not push there.
- Auto-deploy runs on push to `main`.
- Primary stand: `https://изи-никель.рф`.
- Mirror: `https://nornikel.nddev.asia`.
- Host: `ssh curestry`, compose project `/srv/nornikel-kg-search`.
- Ingest/swap runbook: `docs/deployment/full-ingest-runbook.md`.
- High-throughput ingest uses deterministic shard DB files
  (`scripts/ingest_corpus.py --shard-count/--shard-index`) and merges them with
  `scripts/merge_duckdb_shards.py` before swap.

## Quality Notes

- CI must remain offline and deterministic.
- Do not commit `.env`, provider credentials, runtime databases, artifacts, or
  local cache state.
- Do not add legacy fixture seed data back into runtime paths.
- The full evidence graph is never rebuilt from source files — no compute
  resources for a second full ingest. Qdrant payload indexes, scalar
  quantization, DuckDB table reorganization, and targeted reindex of missing
  spans are permitted (they operate on existing data, not source files).
- For answer quality, preserve the cited-sentence and numeric-support invariant.

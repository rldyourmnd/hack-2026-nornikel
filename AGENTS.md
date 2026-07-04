# Repository Instructions

## Project

`hack-2026-nornikel` is the working repository for the Nornikel hackathon
submission. The system is an evidence-led R&D knowledge graph and QA workbench
for mining-and-metallurgy documents.

Repository artifacts are written in English unless they are user-facing Russian
UI copy or corpus examples.

## Engineering Rules

- Code, config, tests, and migrations are the source of truth.
- Do not commit secrets, `.env`, runtime databases, caches, browser artifacts,
  generated local state, or provider credentials.
- Keep changes scoped and follow existing domain/service/adapter boundaries.
- DuckDB is the authoritative ledger; Qdrant is a retrieval index only.
- Vendor clients belong in `src/nornikel_kg/adapters/`.
- Only `src/nornikel_kg/adapters/llm/gateway.py` may import LiteLLM directly.
- Production ingest must not require a local GPU or graphical runtime.
- Do not reintroduce legacy fixture seed data as runtime truth.

## Main Commands

```bash
make install
make ci
make eval-realcase
docker compose config
```

Backend-only checks:

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

Frontend checks:

```bash
cd apps/web && npm run typecheck && npm run build
```

## Runtime Defaults

- Upload limit: `MAX_SOURCE_UPLOAD_BYTES` (default 5 MiB locally, 25 MiB on the
  stand). The bundled web Nginx proxy allows 32 MiB uploads and 300s `/api/`
  proxy timeouts.
- Accepted upload types: `.csv .md .markdown .txt .text .pdf .docx .docm .doc
  .xlsx .xls`.
- PDF ingest defaults to `PDF_PARSE_MODE=pypdfium`, a text-layer parser that does
  not need local ML/GPU dependencies.
- LLM and embedding providers are configured by environment variables. Keep
  model IDs and keys outside git.

## Deployment

- Pushes to `main` auto-deploy through `.github/workflows/deploy.yml`.
- Stand deployment notes: `docs/deployment/nornikel-nddev.md`.
- Batch ingest and atomic swap: `docs/deployment/full-ingest-runbook.md`.
- Build full or sampled graphs into separate `DUCKDB_PATH`,
  `QDRANT_COLLECTION`, and `QDRANT_ENTITY_COLLECTION` values; swap only after
  successful smoke checks.

## Verification Expectations

Run checks matching the touched scope and report exact commands. For changes to
ingest, retrieval, answer verification, source labels, or security-sensitive
paths, include the relevant unit/integration tests and `make ci` when feasible.

`make eval-realcase` requires a running API and verifies the live evidence
contract against organizer-track questions.

<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: d532f3d Merge pull request #23 from rldyourmnd/perf/sharded-ingest
Scope: README.md; AGENTS.md; .claude/CLAUDE.md; apps/web/; services/api/; src/nornikel_kg/; scripts/; docs/deployment/; pyproject.toml; tests/
Area: CORE
-->

# CORE-01-INDEX

## Purpose

Index the durable project knowledge for the Nornikel evidence-led R&D
knowledge-graph submission.

## Source Of Truth

- `README.md`: product overview, architecture, quick start, and public submission context.
- `AGENTS.md`: repository-specific engineering and verification rules.
- `.claude/CLAUDE.md`: concise project notes for assistant sessions.
- `src/nornikel_kg/`: backend domain, ports, services, adapters, resources.
- `services/api/`: FastAPI route layer.
- `apps/web/`: React/Vite workbench.
- `scripts/ingest_corpus.py`: direct container batch ingest for DATA_HACK corpora.
- `scripts/merge_duckdb_shards.py`: merge independently built DuckDB shard ledgers before atomic swap.
- `scripts/run_realcase_eval.py`: live real-corpus honesty gate.
- `docs/deployment/`: stand deployment and ingest/swap runbooks.
- `.serena/memories/`: this current fact set.

## Memory Map

- `ARCH-01-EVIDENCE-MVP.md`: architecture, no-GPU parse path, retrieval and answer flow.
- `DATA-01-EVIDENCE-LEDGER.md`: DuckDB schema and evidence/index contracts.
- `SEC-01-ACL-AND-PROMPT-INJECTION.md`: source labels, prompt-injection, SSRF, provider failure safety.
- `TEST-01-EVALUATION-GATES.md`: current checks and eval commands.
- `RELEASE-01-VALIDATION.md`: deployment, compose, batch ingest, swap, validation.
- `DOCS-01-PLANNING-SOURCE.md`: documentation precedence.
- `TECHDEBT-01-NOW.md`: current verified gaps only.

## Current Behavior

- Runtime stack: FastAPI + DuckDB ledger + Qdrant hybrid retrieval + LiteLLM gateway + React/Vite UI.
- Provider and model IDs are runtime env configuration. Public docs describe OpenAI-compatible interfaces, not account-specific model choices.
- Dense embeddings can be remote (`EMBEDDING_BACKEND=openai`) or local/fake for development and tests. Sparse BM25 remains local.
- Yandex AI Studio is supported as an OpenAI-compatible runtime provider:
  `LiteLLMGateway` forwards `YANDEX_FOLDER_ID` as `OpenAI-Project`, and
  `YandexEmbeddingBackend` defaults to the v2 doc/query embedding pair at 768
  dimensions.
- Legacy fixture seed data and old generated fixtures are deleted from runtime paths.
- Default PDF ingest is no-GPU/no-layout-model: `.pdf` routes to `PyPdfiumFastParser` unless `PDF_PARSE_MODE=docling`.
- Fast graph controls are active: `LLM_EXTRACTION_MODE=source_packet`, `MAX_EXTRACTION_SPANS=400`, `MAX_TABLE_ROWS_PER_SOURCE=400`, `DuckDBLedgerRepository.batch_transaction()`, and `scripts/ingest_corpus.py --sample N`.
- Parallel corpus builds use deterministic ingest sharding:
  `scripts/ingest_corpus.py --shard-count N --shard-index I` writes each shard
  to a separate `DUCKDB_PATH`; `scripts/merge_duckdb_shards.py` merges shard
  ledgers into the final catalog before the atomic swap. Qdrant collection
  creation is race-tolerant for concurrent shard writers.

## Invariants

- DuckDB is authoritative. Qdrant is retrieval-only and must be rejoined back to DuckDB.
- Every answer sentence must cite evidence spans; numbers must be supported by cited text or structured facts.
- Do not commit secrets, `.env`, runtime DBs, browser artifacts, caches, or local state.
- Do not reintroduce legacy fixture data as runtime truth.
- Only `src/nornikel_kg/adapters/llm/gateway.py` may import LiteLLM.

## Verification

- `uv run ruff check .`
- `uv run mypy`
- `uv run pytest`
- `cd apps/web && npm run typecheck`
- `cd apps/web && npm run build`
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`

<!-- Memory Metadata
Last updated: 2026-07-03
Last commit: 3e74473 docs(deploy): DuckDB lock contract and archive-aware batch procedure
Scope: README.md; apps/web/; services/api/; src/nornikel_kg/; eval/; sample_docs/; scripts/;
  tests/; docker-compose.yml; .github/workflows/ci.yml; .env.example; pyproject.toml;
  .serena/plans/; .serena/reviews/; docs/deployment/; .gitignore
Area: CORE
-->

# CORE-01-INDEX

## Purpose

Index the durable project knowledge for the Nornikel Materials KG Search hackathon MVP.

## Source Of Truth

- `README.md`: repository overview, quick start, demo scenario, and implemented scope.
- `AGENTS.md`: Codex-native project instructions and plugin/tooling policy.
- `.claude/CLAUDE.md`: Claude Code project memory and operational commands.
- `apps/web/`: React/Vite analysis workbench.
- `services/api/`: FastAPI route layer.
- `src/nornikel_kg/`: backend domain, ports, adapters, and application services.
- `scripts/ingest_corpus.py`: batch-ingests a real document corpus directory (now `.pdf`,
  `.docx`, `.docm`, `.doc`, `.xlsx`, `.xls`, `.csv`, `.md`, `.markdown`, `.txt`, plus `.zip`/
  multipart-`.zip.NNN`/`.rar` archive expansion) into the ledger inside the API container; it
  fails fast at start if the ledger cannot be opened (the `api` container's persistent DuckDB
  connection makes the script and a running `api` mutually exclusive — see
  `mem:RELEASE-01-VALIDATION`).
- `eval/`: legacy YAML gold/adversarial fixtures; not read by any code path (`mem:TEST-01-EVALUATION-GATES`).
- `sample_docs/synthetic/`: original P0 fixture. `sample_docs/synthetic_v2/`: W5 17-source synthetic corpus with `manifest.json`.
- `tests/`: unit and integration tests (141 passed, 4 skipped at `3e74473`, live-run verified).
- `docs/deployment/nornikel-nddev.md`: primary live-stand deployment contract, now documenting
  the DuckDB lock contract and the archive-aware batch-ingest procedure.
- `.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md`: full-track requirement brief («Научный
  клубок») and gap analysis G1-G10 against the real `DATA_HACK/` corpus.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`: the accuracy/SOTA overhaul plan (waves A-D,
  landed as PR #15) plus wave E (archive/legacy-format ingestion, PR #16) tracked in its own
  commits — see Current Behavior below.
- `.serena/reviews/`: tracked plan critical review and research evidence register.

## Entry Points

- `mem:ARCH-01-EVIDENCE-MVP`: architecture, module boundaries, ports/adapters, and stack decisions.
- `mem:DATA-01-EVIDENCE-LEDGER`: evidence IDs, DuckDB ledger, graph/entity schema, and answer claims.
- `mem:SEC-01-ACL-AND-PROMPT-INJECTION`: source-label filtering, prompt-injection, and internal-document safety invariants.
- `mem:TEST-01-EVALUATION-GATES`: required checks, metrics, and acceptance gates.
- `mem:DOCS-01-PLANNING-SOURCE`: planning-doc ownership and current implementation status.
- `mem:RELEASE-01-VALIDATION`: validation, CI, Compose, and deployment checks.
- `mem:TECHDEBT-01-NOW`: verified current gaps and migration triggers.

## Current Behavior

Since the last sync (`41ee7ac`), ten commits landed two merged feature branches plus two
follow-on fixes, all verified against the working tree at `3e74473`:

- **PR #15 "accuracy/SOTA overhaul waves A-D"** (`2368791` plan doc, `41b3acd` wave A extraction
  accuracy, `944e6f0` wave B retrieval/resolution accuracy, `93f3f87` wave C answer/graph
  honesty, `12bc5c1` wave D provable quality gates + demo UI, merged `b611591`). Research
  verdicts (kept GLiNER `gliner_multi-v2.1`, kept `deepvk/USER-bge-m3` embeddings, added
  `BAAI/bge-reranker-v2-m3` reranker) are tracked in `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`.
- **`b7b12d6` perf fix**: `RetrievalService.index_source` no longer re-embeds the entities
  collection per source (`include_entities` param, default `False`); `reindex_all()` indexes
  entities once at the end.
- **PR #16 "archive and legacy-format corpus ingestion wave E"** (`2e5458a`, merged `65694a7`):
  `.zip`/multipart-`.zip.NNN`/`.rar` archive expansion, `.xlsx`/`.xls` spreadsheet parsing,
  legacy `.doc` text extraction, `.docm` routed through the Docling `.docx` path.
- **`1db832d` fix**: `scripts/ingest_corpus.py` now calls `get_ledger_repository().migrate()`
  up front and raises `SystemExit` with a clear message if the ledger cannot be opened (the
  `api` container's persistent DuckDB connection makes the batch script and a running `api`
  mutually exclusive).
- **`3e74473` docs**: `docs/deployment/nornikel-nddev.md` documents the DuckDB lock contract and
  the `stop api` / `run --rm --no-deps` batch-ingest procedure, and routes vector reindex through
  `POST /sources/reindex-all` instead of a direct `docker compose exec`.

See `mem:ARCH-01-EVIDENCE-MVP`, `mem:DATA-01-EVIDENCE-LEDGER`, `mem:TECHDEBT-01-NOW` for the
per-module detail of each wave.

`uv run pytest` passes **141 tests, 4 skipped** at `3e74473` (verified by a live run in this sync
pass); `uv run ruff check .` and `uv run mypy` both pass clean (also verified live in this sync
pass). Local `main` and `origin/main` are in sync (`git rev-list --left-right --count
origin/main...main` -> `0\t0`, verified).

## Contracts And Data

Full flow: React/Vite workbench -> FastAPI (`/sources/upload`, `/sources/import-url`,
`/sources/{id}/enrich`, `/sources/reindex-all`, `/qa/ask`, `/entities/search`, `/entities/{id}`,
`/graph/neighborhood`, `/graph/timeline`, `/gaps/analyze`, `/eval/summary`) -> DuckDB-backed
evidence ledger + entity/relation graph -> optional Qdrant hybrid retrieval (dense + BM25
sparse, optional cross-encoder rerank) -> deterministic-or-LLM answer synthesis -> claim
verification (citation coverage + numeric-mismatch gate) -> answer-run persistence.

Upload accepts `.csv`, `.md`, `.markdown`, `.txt`, `.text`, `.pdf`, `.docx`, `.docm`, `.doc`,
`.xlsx`, `.xls` with filename/MIME/size validation (`services/api/routes/sources.py`);
`MAX_SOURCE_UPLOAD_BYTES` code default is `5242880` bytes; bundled web Nginx sets
`client_max_body_size 32m` and `proxy_read_timeout 300s` for `/api/`.

## Invariants

- Do not treat Markdown chunks as source of truth; they are convenience views only.
- Every answer sentence must map to exact evidence IDs, and every number in a sentence must
  literally appear in the cited evidence text (`domain/answer_claims.py:sentence_numbers_supported`),
  unless the sentence is fact-backed (deterministic assembler, carries `supporting_fact_ids`).
- DuckDB is authoritative for facts and provenance; if DuckDB and Qdrant disagree, DuckDB wins.
- Qdrant is retrieval-only; NetworkX is graph materialization-only, rebuilt on demand from DuckDB.
- React/Vite and FastAPI are P0 UI/API layers, not P1.
- No OCR: PDFs without a text layer are quarantined, never OCR'd (`NoTextLayerError`); images
  inside archives are counted as no-OCR skips by `scripts/ingest_corpus.py`.
- Only `src/nornikel_kg/adapters/llm/gateway.py` may `import litellm`.
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()`; the connection
  is persistent and shared, so external processes (including `scripts/ingest_corpus.py`) must
  stop the `api` container before opening the DuckDB file directly.

## Change Rules

Update this index whenever a new durable memory is added, renamed, split, or deleted.

## Verification

- `make ci`: verifies backend ruff/mypy/pytest and frontend typecheck/build.
- `make eval`: runs `scripts/run_eval.py` (17 hardcoded `EVAL_QUESTIONS`, incl. numeric-constraint,
  conflict-surfacing, and adversarial prompt-injection cases).
- `docker compose config`: verifies Compose syntax without requiring local secrets.
- `uv run pytest`: 141 tests pass, 4 skipped at `3e74473` (live-run verified).
- `uv run ruff check .` / `uv run mypy`: both clean at `3e74473` (live-run verified).

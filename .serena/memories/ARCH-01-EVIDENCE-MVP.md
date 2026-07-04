<!-- Memory Metadata
Last updated: 2026-07-05
Last commit: 67f08b0 fix(llm): map claude effort for dataeyes
Scope: scripts/ingest_corpus.py; scripts/merge_duckdb_shards.py; src/nornikel_kg/services/ingestion_service.py; src/nornikel_kg/adapters/pdf_fast/; src/nornikel_kg/adapters/llm/gateway.py; src/nornikel_kg/adapters/embeddings/yandex.py; src/nornikel_kg/services/extraction_service.py; src/nornikel_kg/services/retrieval_service.py; src/nornikel_kg/services/qa_service.py; src/nornikel_kg/adapters/duckdb/repositories.py; services/api/; apps/web/
Area: ARCH
-->

# ARCH-01-EVIDENCE-MVP

## Purpose

Capture the architecture contract for the evidence-first R&D workbench.

## Source Of Truth

- `src/nornikel_kg/domain/`: IDs, evidence, models, extraction vocabularies, claims, security, quantities, dates, table facts.
- `src/nornikel_kg/ports/`: parser, ledger, extraction, LLM, retrieval protocols.
- `src/nornikel_kg/services/`: orchestration services; vendor imports stay out of this layer.
- `src/nornikel_kg/adapters/`: DuckDB, Qdrant, LiteLLM, embeddings, parsers, reranker, URL fetcher.
- `services/api/main.py` and `services/api/routes/`: FastAPI HTTP boundary.
- `apps/web/src/app/ui/App.tsx`: frontend route shell.

## Entry Points

- `services/api/main.py:create_app`: mounts health, QA, sources, graph, entities, gaps, eval, stats routes.
- `services/api/routes/query.py:/qa/ask`: answer API.
- `services/api/routes/sources.py`: upload/import/archive/delete/reindex endpoints.
- `src/nornikel_kg/services/runtime.py`: env-driven wiring.
- `src/nornikel_kg/services/ingestion_service.py:IngestionService.ingest_upload`: parse -> ledger -> extraction -> retrieval index.
- `src/nornikel_kg/services/extraction_service.py:ExtractionService.process_source`: entity/relation extraction.
- `src/nornikel_kg/services/qa_service.py:EvidenceQAService.ask`: filter/retrieve/compose/verify/persist answer.

## Current Behavior

- `.pdf` ingest defaults to `PyPdfiumFastParser`, a pypdfium2 text-layer parser with no OCR, no ML layout model, no GPU, and no graphical-system dependency. The pypdfium2 call runs in a subprocess so a `libpdfium` crash cannot kill the main ingest process.
- DOCX/DOCM/PPTX use the document parser; XLS/XLSX use the spreadsheet parser; legacy DOC uses antiword/catdoc; URL import uses trafilatura after controlled SSRF-safe fetch.
- `LLM_EXTRACTION_MODE=source_packet` is the default: one guided-JSON call over a representative source packet, then mentions/relations are attributed to spans containing the mention text. `span_budget` opts into deeper per-span extraction.
- `MAX_EXTRACTION_SPANS` and `MAX_TABLE_ROWS_PER_SOURCE` default to 400 and bound graph work for large files. All emitted spans are still stored and indexed for retrieval.
- `DuckDBLedgerRepository.batch_transaction()` wraps one source's graph write burst in a single transaction under the process lock.
- High-throughput corpus builds should run multiple independent ingest shards:
  each shard uses its own `DUCKDB_PATH`, all shards can write to one fresh
  Qdrant collection, and `scripts/merge_duckdb_shards.py` merges the ledgers.
  This is the supported way to use more no-GPU server resources without
  violating DuckDB's single-file writer constraints.
- `RetrievalService` indexes spans into Qdrant, prefixes source title for retrievability, and rejoins hits back to DuckDB before trust.
- `YandexEmbeddingBackend` uses Yandex AI Studio text vectorization v2 with
  `text-embeddings-v2-doc` for indexed content, `text-embeddings-v2-query` for
  queries, and `YANDEX_EMBED_DIM=768` by default.
- `LiteLLMGateway` supports Yandex AI Studio's OpenAI-compatible endpoint by
  adding `OpenAI-Project: $YANDEX_FOLDER_ID` for `*.yandex.net` providers while
  keeping the standard LiteLLM `api_base`/`api_key` call path.
- `LiteLLMGateway` forwards `LLM_REASONING_EFFORT` when set. For `gpt-5*`
  model IDs it uses `temperature=1` because LiteLLM/OpenAI-compatible GPT-5
  chat completions reject `temperature=0`; older extraction models keep
  temperature zero.
- DataEyes Claude/Sonnet answer models are exposed through an OpenAI-compatible
  LiteLLM route, but their effort control is Anthropic-style:
  `output_config={"effort": LLM_REASONING_EFFORT}`. Do not send
  OpenAI-style `reasoning_effort` to Claude/Sonnet models; DataEyes rejects it.
  `openai/claude-sonnet-5` with `LLM_REASONING_EFFORT=medium` was verified as
  the fast answer-model path on the stand.
- `LLMAnswerComposer` and `ClaimVerifier` enforce cited-span and number-support gates. Answer synthesis retries one transient `LLMError` or raw provider exception, then degrades to deterministic/rule-only behavior on the second failure so `/qa/ask` does not 500.

## Contracts

- `AskRequest` and `AskResponse` live in `src/nornikel_kg/domain/models.py`.
- Retrieval collections are selected by `QDRANT_COLLECTION` and `QDRANT_ENTITY_COLLECTION`; use a new collection when vector dimension changes.
- For Yandex AI Studio LLMs, model IDs are runtime env values such as
  `LLM_EXTRACTION_MODEL=openai/gpt://<folder>/deepseek-v4-flash`; folder IDs and
  credentials stay outside git.
- Source labels are deployment-floor filtered by `JURY_ALLOWED_LABELS` and may only be narrowed by request `allowed_labels`.
- `/health` reports readiness flags and backend class only; it must not expose exact
  provider model IDs. Its LLM readiness uses `LLMSettings`, so canonical env vars and
  supported legacy aliases are interpreted the same way as runtime wiring.

## Invariants

- No answer may trust Qdrant text without DuckDB rejoin and label filtering.
- No-GPU/no-local-graphics constraint applies to production ingest.
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()`.

## Verification

- `uv run pytest tests/unit/test_corpus_formats.py tests/unit/test_openai_embedding_backend.py`
- `uv run pytest tests/unit/test_answer_honesty.py tests/unit/test_claim_verifier.py`
- Full gate: `uv run ruff check . && uv run mypy && uv run pytest`.

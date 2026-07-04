<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 4e4a038
Scope: src/nornikel_kg/services/ingestion_service.py; src/nornikel_kg/adapters/pdf_fast/; src/nornikel_kg/services/extraction_service.py; src/nornikel_kg/services/retrieval_service.py; src/nornikel_kg/services/qa_service.py; src/nornikel_kg/adapters/duckdb/repositories.py; services/api/; apps/web/
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

- `.pdf` ingest defaults to `PyPdfiumFastParser`, a pypdfium2 text-layer parser with no OCR, no ML layout model, no GPU, and no graphical-system dependency.
- DOCX/DOCM/PPTX use the document parser; XLS/XLSX use the spreadsheet parser; legacy DOC uses antiword/catdoc; URL import uses trafilatura after controlled SSRF-safe fetch.
- `LLM_EXTRACTION_MODE=source_packet` is the default: one guided-JSON call over a representative source packet, then mentions/relations are attributed to spans containing the mention text. `span_budget` opts into deeper per-span extraction.
- `MAX_EXTRACTION_SPANS` and `MAX_TABLE_ROWS_PER_SOURCE` default to 400 and bound graph work for large files. All emitted spans are still stored and indexed for retrieval.
- `DuckDBLedgerRepository.batch_transaction()` wraps one source's graph write burst in a single transaction under the process lock.
- `RetrievalService` indexes spans into Qdrant, prefixes source title for retrievability, and rejoins hits back to DuckDB before trust.
- `LLMAnswerComposer` and `ClaimVerifier` enforce cited-span and number-support gates. Provider failures degrade to deterministic/rule-only behavior where callers catch `LLMError`.

## Contracts

- `AskRequest` and `AskResponse` live in `src/nornikel_kg/domain/models.py`.
- Retrieval collections are selected by `QDRANT_COLLECTION` and `QDRANT_ENTITY_COLLECTION`; use a new collection when vector dimension changes.
- Source labels are deployment-floor filtered by `JURY_ALLOWED_LABELS` and may only be narrowed by request `allowed_labels`.
- `/health` reports readiness flags and backend class only; it must not expose exact provider model IDs.

## Invariants

- No answer may trust Qdrant text without DuckDB rejoin and label filtering.
- No-GPU/no-local-graphics constraint applies to production ingest.
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()`.

## Verification

- `uv run pytest tests/unit/test_corpus_formats.py tests/unit/test_openai_embedding_backend.py`
- `uv run pytest tests/unit/test_answer_honesty.py tests/unit/test_claim_verifier.py`
- Full gate: `uv run ruff check . && uv run mypy && uv run pytest`.

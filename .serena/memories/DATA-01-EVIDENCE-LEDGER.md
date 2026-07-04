<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 97407f4
Scope: src/nornikel_kg/domain/; src/nornikel_kg/adapters/duckdb/; src/nornikel_kg/services/extraction_service.py; src/nornikel_kg/services/retrieval_service.py; scripts/ingest_corpus.py
Area: DATA
-->

# DATA-01-EVIDENCE-LEDGER

## Purpose

Capture evidence identity, DuckDB ledger schema, graph/fact persistence, and retrieval-index contracts.

## Source Of Truth

- `src/nornikel_kg/domain/ids.py`: stable source/artifact/span/fact/claim IDs.
- `src/nornikel_kg/domain/models.py`: API/domain payload models.
- `src/nornikel_kg/domain/evidence.py`: `EvidenceSpanFactory`.
- `src/nornikel_kg/adapters/duckdb/migrations/001_init.sql`: sources, evidence spans, property measurements, effect claims, answer claims.
- `src/nornikel_kg/adapters/duckdb/migrations/002_graph.sql`: runs, artifacts, entities, aliases, relations, extraction claims, answer/eval runs.
- `src/nornikel_kg/adapters/duckdb/migrations/003_numeric_facts.sql`: persisted generic numeric facts.
- `src/nornikel_kg/adapters/duckdb/migrations/004_graph_indexes.sql`: relation indexes for SQL graph traversal.
- `src/nornikel_kg/adapters/duckdb/repositories.py`: single DuckDB adapter and persistence boundary.
- `scripts/ingest_corpus.py`: real-corpus batch ingestion.

## Entry Points

- `DuckDBLedgerRepository.ingest_source_bytes`: text/CSV ingest.
- `DuckDBLedgerRepository.ingest_parsed_document`: parsed document/table ingest.
- `DuckDBLedgerRepository.batch_transaction`: one-source transaction for graph extraction writes.
- `DuckDBLedgerRepository.list_evidence_spans_by_ids`: targeted retrieval rejoin.
- `DuckDBLedgerRepository.corpus_stats`: stats API backing `/stats/overview`.
- `RetrievalService.index_source` / `reindex_all`: Qdrant indexing from DuckDB spans/entities.

## Current Behavior

- Legacy fixture seed infrastructure is removed from the active code path; clean ledgers should have no fixture sources.
- Default PDF parse produces text blocks with parser profile `pypdfium_fast_v1`. It preserves page/locator provenance but does not produce structured PDF table rows or numeric facts.
- Spreadsheet and Docling table paths produce `table_row` evidence and `numeric_facts`, capped by `MAX_TABLE_ROWS_PER_SOURCE`.
- All ingested spans are stored and indexed, but graph extraction processes only the first `MAX_EXTRACTION_SPANS` source spans by default.
- A source's graph write phase runs in one DuckDB transaction, reducing commit churn under the single persistent connection.
- Qdrant points are retrieval units only; stale or mismatched vectors must never override DuckDB truth.

## Contracts And Data

- `sources`: `source_id`, title, document type, sha, label, year/geography metadata.
- `evidence_spans`: span ID, source, artifact, type, visible text, page, locator JSON, validation, confidence, label.
- `numeric_facts`: source/span, subject, property, value, unit, qualifier, validation.
- `entities`/`entity_aliases`/`relations`: extracted graph; relations carry evidence span IDs.
- `answer_runs`/`answer_claims`: verification trail for answered questions and verified claims.

## Invariants

- Evidence IDs and source IDs are stable and content/provenance based.
- Deleting a source must cascade DuckDB graph/fact references and best-effort delete Qdrant units.
- Do not average or overwrite conflicting measurements silently.
- Do not create LLM facts without supporting span IDs.

## Verification

- `uv run pytest tests/integration/test_duckdb_ledger.py`
- `uv run pytest tests/unit/test_table_facts.py tests/unit/test_parameter_constraints.py`
- `uv run pytest tests/unit/test_retrieval_service.py`

<!-- Memory Metadata
Last updated: 2026-07-03
Last commit: 3e74473 docs(deploy): DuckDB lock contract and archive-aware batch procedure
Scope: src/nornikel_kg/domain/; src/nornikel_kg/adapters/duckdb/;
  src/nornikel_kg/resources/dictionaries/; src/nornikel_kg/services/; sample_docs/; eval/;
  scripts/ingest_corpus.py
Area: DATA
-->

# DATA-01-EVIDENCE-LEDGER

## Purpose

Capture evidence identity, artifact memory, scientific schemas, graph/entity/relation storage,
retrieval-unit indexing, and answer-run/eval persistence in the DuckDB ledger, after the
accuracy/SOTA overhaul (waves A-D) and archive/legacy-format ingestion (wave E).

## Source Of Truth

- `src/nornikel_kg/domain/ids.py`: stable `source_id`, `artifact_id`, `span_id`, `fact_id`,
  `claim_id` helpers.
- `src/nornikel_kg/domain/models.py`: Pydantic API/domain payload models, including
  `AskFilters.geography`/`year_from`/`year_to` and `AnswerVerification.numeric_mismatch_count`.
- `src/nornikel_kg/domain/evidence.py`: `EvidenceSpanFactory`.
- `src/nornikel_kg/domain/normalization.py`: `canonical_key()` mention-normalization helper —
  strips edge punctuation and folds Cyrillic->Latin homoglyphs only inside mixed-script tokens
  (`mem:ARCH-01-EVIDENCE-MVP`).
- `src/nornikel_kg/domain/quantities.py` (new): unit canonicalization (`normalize_unit`) and
  unit-bearing numeric-constraint parsing/matching (`parse_numeric_constraints`,
  `satisfies_constraints`).
- `src/nornikel_kg/domain/dates.py` (new): deterministic RU/EN year/date extraction
  (`extract_date`, `extract_year`, `extract_year_from_filename`).
- `src/nornikel_kg/domain/extraction.py`: entity/relation type vocabularies (`ENTITY_TYPES`,
  `RELATION_TYPES`) now include `publication`/`DESCRIBED_IN`, and the LLM extraction JSON schema
  is strict-valid (`mem:ARCH-01-EVIDENCE-MVP`).
- `src/nornikel_kg/domain/analysis.py`: `ConflictDetector`/`GapAnalyzer` — regime bucketing
  strips the `reg_`/`regime_` prefix; numeric-disagreement conflicts require matching canonical
  unit and non-empty equal methods.
- `src/nornikel_kg/adapters/duckdb/migrations/001_init.sql`, `002_graph.sql`: ledger and
  graph/knowledge schema (unchanged this wave; `sources.year`/`geography` were added additively
  in the prior wave).
- `src/nornikel_kg/adapters/duckdb/dictionary_loader.py`: idempotent entity/alias seeding.
- `src/nornikel_kg/adapters/duckdb/repositories.py`: `DuckDBLedgerRepository` — the single
  DuckDB adapter for ledger, graph, retrieval-unit listing, and eval persistence. Gained
  `set_entity_metadata`, `list_evidence_spans_by_ids`, cascade-aware `_delete_source_records`,
  and `year`/`geography` in `list_sources()`/`SourceSummary`.
- `src/nornikel_kg/resources/dictionaries/{materials,regimes,properties,equipment}.yml`:
  dictionary-seeded ontology, unchanged this wave (last extended in the real-corpus hardening
  wave, `58760b3`; geomechanics terms are still not covered, `mem:TECHDEBT-01-NOW`).
- `sample_docs/synthetic/`: original P0 fixture. `sample_docs/synthetic_v2/`: W5 corpus.
- `scripts/ingest_corpus.py`: batch real-corpus ingester; now archive-aware and fail-fast on the
  DuckDB lock (see `mem:RELEASE-01-VALIDATION`).
- `eval/*.yml`: legacy fixtures, no longer read by any code (`mem:TEST-01-EVALUATION-GATES`).

## Entry Points

- `DuckDBLedgerRepository.seed_synthetic_fixture` / `ingest_source_bytes`: CSV/Markdown/text
  ingest into `sources`/`evidence_spans`/`property_measurements`/`effect_claims`.
- `DuckDBLedgerRepository.ingest_parsed_document(...)`: writes text/table-row evidence spans
  from a `ParsedDocument` (now also fed by `SpreadsheetDocumentParser` and `LegacyDocParser`
  output, in addition to Docling).
- `DuckDBLedgerRepository.set_entity_metadata(entity_id, updates)`: merges keys into
  `entities.metadata_json` (`SELECT` current JSON, `dict.update`, `UPDATE ... SET
  metadata_json`); used by `ExtractionService._link_publication` to store a publication's
  extracted `year`/`date`.
- `DuckDBLedgerRepository.list_evidence_spans_by_ids(span_ids)`: targeted rejoin for retrieval
  hits (never scans the full `evidence_spans` table); used by
  `RetrievalService.retrieve_span_ids`.
- `DuckDBLedgerRepository.set_source_metadata(source_id, *, year, geography)`: unchanged
  `COALESCE` update contract from the prior sync.
- `DuckDBLedgerRepository.source_metadata() -> dict[str, dict[str, Any]]`: unchanged; consumed
  by `DemoQAService._apply_source_scope` via the `RunRecorderProtocol` contract.
- `DuckDBLedgerRepository._connect()`: still a persistent-connection `@contextmanager` behind a
  class `_db_lock` (`threading.RLock`), unchanged from `f40ab72` — the process holding this
  repository instance holds the DuckDB file lock for its lifetime.
- `DuckDBLedgerRepository.load_demo_packet`: returns the full evidence/graph packet used by
  `DemoQAService`; returns an empty `EvidenceLedgerPacket` when the ledger is empty.
- `load_dictionaries(connection, dictionaries_dir=None)` / `resolve_alias(connection, mention)`:
  dictionary seeding/lookup helpers.
- Entity/relation repository methods: `find_entity`, `get_entity`, `create_entity`,
  `merge_entity_evidence`, `insert_relation`, `insert_extraction_claim`, `search_entities`,
  `list_graph_entities`, `list_graph_relations`, `list_alias_index`.
- Eval/answer persistence: `record_answer_run`/`get_answer_run`; `store_eval_result`/
  `latest_eval_summary`.

## Current Behavior

CSV uploads still require the P0 measurement columns and become `table_row` spans plus
source-scoped measurements/effects. PDF/DOCX/DOCM uploads route through `DoclingDocumentParser`
(a PDF with no extractable text layer is quarantined with zero evidence spans); XLSX/XLS route
through `SpreadsheetDocumentParser`; legacy `.DOC` routes through `LegacyDocParser` (quarantines
via `ParserError` when neither `antiword` nor `catdoc` is installed, or the extracted text is
empty).

Every parsed ingest calls `_apply_source_metadata`/`_set_year_geography` in `IngestionService`,
which now derives the year via `domain.dates.extract_year_from_filename` (filename wins) then
`domain.dates.extract_year` (year-marker-guarded scan of the head text), falling back to a
parsed-metadata date when present; the Cyrillic-vs-Latin geography heuristic now folds `ё` into
the Cyrillic count. `sources.year`/`sources.geography` columns are unchanged, additively
migrated in the prior wave.

Extraction writes `entities`/`entity_aliases`/`relations`/`extraction_claims` rows keyed by
stable IDs; every source gets one `publication` entity plus `DESCRIBED_IN`/`AUTHORED_BY`
relations via `ExtractionService._link_publication`, which now also writes the publication's
extracted `year`/`date` into `entities.metadata_json` via `set_entity_metadata`
(`mem:ARCH-01-EVIDENCE-MVP`). `publication`/`DESCRIBED_IN` are now part of `domain/extraction.py`'s
`ENTITY_TYPES`/`RELATION_TYPES` tuples, so this path is no longer outside the declared
vocabulary. `EntityResolutionService` gained a semantic-fallback stage (cosine-matched via
Qdrant, `mem:ARCH-01-EVIDENCE-MVP`) before falling back to `create_entity`; it still never
merges entities across `entity_type`.

Retrieval indexing writes into two Qdrant collections when `EMBEDDING_BACKEND` is not `off`:
`evidence_units` and `entities`. `RetrievalService.index_source(..., include_entities=False)` no
longer re-embeds the entities collection per source (perf fix `b7b12d6`); `reindex_all()`
re-indexes every source's spans then indexes entities once. Indexed evidence text is prefixed
with the source title for retrievability of short spans. Sparse (BM25) vectors now use
`SPARSE_LANGUAGE=russian` at both index (`embed_sparse`) and query (`embed_sparse_query`) time.

Deleting a source (`DuckDBLedgerRepository._delete_source_records`) now cascades: it collects
the source's `span_id`s before deleting `evidence_spans`, then strips those span IDs out of
every `relations.evidence_span_ids_json` and `entities.evidence_span_ids_json` — rows (and, for
`ent_`-prefixed non-dictionary entities, their aliases and relations) whose evidence empties out
are deleted; dictionary-seeded entities (stable IDs, not `ent_`-prefixed) are kept even if their
evidence empties, since migrations reseed them. `extraction_claims` and `ingestion_runs` rows for
the source are also deleted. `DELETE /sources/{id}` additionally best-effort deletes the
source's Qdrant units.

## Real-Corpus Ontology Extension (2026-07-03, commit `58760b3` — unchanged this sync)

`src/nornikel_kg/resources/dictionaries/materials.yml`/`regimes.yml`/`properties.yml`/
`equipment.yml` cover pyrometallurgy, electrowinning, flotation/beneficiation, and desalination
domains (17/15/14/9 entries respectively, verified counts unchanged from the prior sync).
**Geomechanics-specific terms are still not covered** (verified: no `геомех`/`geomechanic`/
`горн` alias hits in any dictionary file this sync pass), so gap G1 from
`.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md` remains only partially closed.

`tests/unit/test_scope_and_constraints.py` still verifies dictionary resolution and
publication/author linking (12 lines of diff this wave adjust assertions for the new unit
canonicalization, not the dictionary content itself).

## W5 Synthetic Corpus

`scripts/generate_synthetic_docs.py` deterministically writes `sample_docs/synthetic_v2/`
(17 committed sources per `manifest.json`), unchanged this sync pass;
`tests/integration/test_synthetic_v2_corpus.py` verifies manifest-vs-committed consistency and
offline/docling/trafilatura-gated ingestion behavior.

## Contracts And Data

Separate IDs for `source_id`, `artifact_id`, `span_id`, `fact_id`, `claim_id`. Table rows/cells
remain first-class evidence units. `entities` rows carry `entity_id`, `entity_type`,
`canonical_key`, `canonical_name`, `metadata_json` (publications now carry `year`/`date` keys),
`evidence_span_ids_json`, `confidence`, `validation_status`. `sources` rows carry `year`/
`geography` (nullable, additively migrated in the prior wave). Gap analysis (`GapAnalyzer`) only
considers dictionary-seeded entities (IDs not starting with `ent_`), so `publication`/`person`
entities never appear in the coverage matrix.

## Invariants

- Do not reconstruct evidence from Qdrant text alone; hybrid search hits are always rejoined
  against DuckDB and re-filtered by `security_label` before being trusted.
- Do not overwrite conflicting measurements or average them silently.
- Do not call `duckdb.connect(...)` directly from repository methods; always go through
  `DuckDBLedgerRepository._connect()`. The connection is persistent per instance, so external
  out-of-process access to the DuckDB file (including `scripts/ingest_corpus.py`) is not
  possible while an instance holding the lock (e.g. the running `api` service) is alive — the
  batch script now fails fast with a clear message instead of hanging or silently corrupting
  state (`1db832d`).
- Numeric measurements require property, value, unit, and supporting spans; numeric-constraint
  filtering only ever applies a constraint whose canonical unit matches the measurement's.
- LLM-extracted facts without existing EvidenceSpan IDs are rejected; invalid LLM extraction
  payloads get one retry with validation feedback, then are recorded with `status="rejected"`
  in `extraction_claims` and fall back to rule-only mentions.
- `set_source_metadata` uses `COALESCE`, so passing `None` for `year`/`geography` never clears a
  previously-set value.
- Dictionary seeding is upsert-only; entity resolution never merges across `entity_type`, and
  semantic merges never happen for digit-bearing or short (<4 char) canonical keys.
- Deleting a source cascades into `relations`/`entities` evidence-span references,
  `extraction_claims`, and `ingestion_runs`, but never deletes dictionary-seeded entities.

## Change Rules

Extend `sample_docs/synthetic_v2/manifest.json` and
`tests/integration/test_synthetic_v2_corpus.py` together whenever the synthetic corpus changes.
Extend `tests/unit/test_scope_and_constraints.py` and the relevant dictionary YAML together
whenever the real-corpus ontology changes. Add migrations and domain tests before adding
parser/indexing code that writes new fact types.

## Verification

- `uv run pytest`: 141 tests pass, 4 skipped, at `3e74473` (live-run verified in this sync pass).
- `make eval`: `scripts/run_eval.py` — 17 hardcoded questions against the synthetic corpus only.
- `tests/unit/test_dictionary_loader.py`, `tests/unit/test_scope_and_constraints.py`: dictionary
  seeding/idempotency/alias resolution, real-domain ontology resolution, publication/author
  linking, geography/year scope filters, numeric constraint filters.
- `tests/unit/test_quantities_and_dates.py` (new, 9 test functions): unit canonicalization,
  numeric-constraint parsing/matching, year/date extraction guards.
- `tests/unit/test_extraction_accuracy.py` (new, 9 test functions): alias word-boundary matching,
  author-extraction affiliation gating, canonical-key homoglyph folding.
- `tests/unit/test_retrieval_and_resolution_accuracy.py` (new, 6 test functions): BM25 language,
  reranker wiring, semantic entity-resolution thresholds/veto.
- `tests/unit/test_corpus_formats.py` (new, 7 test functions): archive expansion (plain zip,
  multipart zip, zip-slip guard, corrupt rar), spreadsheet parsing, legacy-doc `ParserError`,
  `.docm` routing.
- `tests/unit/test_entity_resolution.py`, `tests/unit/test_extraction_service.py`,
  `tests/unit/test_retrieval_service.py`, `tests/unit/test_answer_composer.py`,
  `tests/unit/test_ingestion_service.py`: unit coverage for services.
- `tests/integration/test_graph_api.py`, `tests/integration/test_ingest_api.py`,
  `tests/integration/test_analytics_api.py` (new, 7 test functions: `/gaps`, `/graph/timeline`,
  `/sources/{id}/enrich`, `/sources/reindex-all`): API-level coverage.

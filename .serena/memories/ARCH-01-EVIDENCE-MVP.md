<!-- Memory Metadata
Last updated: 2026-07-04\nLast commit: bb45bce docs: refresh all documentation to the shipped state
Scope: apps/web/; services/api/; src/nornikel_kg/; docker-compose.yml; .github/workflows/ci.yml;
  .github/workflows/deploy.yml; pyproject.toml; .serena/newproj/nornikel-kg-search/; README.md
Area: ARCH
-->

# ARCH-01-EVIDENCE-MVP

## Purpose

Capture the current architecture contract for the evidence-first materials research workbench
after the accuracy/SOTA overhaul (waves A-D) and the archive/legacy-format ingestion wave (E).

## Source Of Truth

- `.serena/newproj/nornikel-kg-search/18_IMPLEMENTATION_SPEC.md`: original scaffold decisions.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`: research verdicts and wave A-D/E scope.
- `src/nornikel_kg/ports/`: port protocols (`ledger.py`, `llm.py`, `parser.py`, `retrieval.py`,
  `extraction.py`). `ports/retrieval.py` gained `embed_sparse_query` (query-side BM25 vectors,
  distinct from document-side `embed_sparse`) and `VectorIndexPort.dense_search` (raw cosine
  scores, used for entity-resolution thresholding).
- `src/nornikel_kg/adapters/`: concrete adapters per port, now including
  `adapters/reranker/cross_encoder.py`, `adapters/spreadsheet/parser.py`,
  `adapters/legacy_doc/parser.py`.
- `src/nornikel_kg/services/`: application services (orchestration only, no vendor imports
  outside adapters), now including `services/archive_expansion.py`.

## Entry Points

- `src/nornikel_kg/domain/quantities.py`: `normalize_unit`, `parse_numeric_constraints`,
  `satisfies_constraints`. Unit canonicalization collapses physically equivalent spellings
  (`мг/дм3`/`мг/дм³`/`mg/l` -> `мг/л`, `°с`/`°c`/`℃` -> `c`, etc., `_UNIT_EQUIVALENCE` dict).
  `parse_numeric_constraints` is precision-first: a constraint without an explicit recognized
  unit is never returned, so «до 2020 года» cannot silently filter unrelated measurements.
  `satisfies_constraints` only applies a constraint when its canonical unit matches the
  measurement's canonical unit.
- `src/nornikel_kg/domain/dates.py`: `extract_date`/`extract_year`/`extract_year_from_filename`.
  Deterministic narrow-regex RU/EN date extraction (ISO, `DD.MM.YYYY`, RU month names, EN month
  names); bare 4-digit years are only trusted next to an explicit year marker
  (`_YEAR_MARKER_RE`: «2023 г.», «в ... году», «© 2021») or an ISO/DMY date elsewhere in the
  text, so sample codes and Kelvin temperatures («1963 K») do not masquerade as years
  (`MIN_YEAR=1950`, `MAX_YEAR=2027`).
- `src/nornikel_kg/domain/normalization.py`: `canonical_key` now strips edge quotes/punctuation
  (`_EDGE_PUNCT_RE`) and folds Cyrillic->Latin homoglyphs (`_fold_homoglyphs`) **only** in tokens
  that already contain a Latin letter — pure-Cyrillic tokens (including alloy codes like «МН30»)
  stay Cyrillic, so they still resolve through the alias table rather than being corrupted.
- `src/nornikel_kg/domain/extraction.py`: `ENTITY_TYPES` now includes `"publication"`;
  `RELATION_TYPES` includes `"DESCRIBED_IN"` — both vocabularies reconciled with what
  `ExtractionService._link_publication` actually writes.
  `EXTRACTION_JSON_SCHEMA` is strict-valid: no `confidence` property is requested from the model
  (assigned in code instead), and every object schema's `required` list matches its `properties`
  keys exactly (enforced at the schema-definition level, plus generically by
  `adapters/llm/gateway.py:_strictify`, which sets `required = list(properties.keys())` for
  every object node).
- `src/nornikel_kg/adapters/llm/gateway.py`: `LiteLLMGateway.generate_json` — `_strictify` fixes
  both `additionalProperties` and the required-keys contract (root cause of prior
  schema-rejected extraction calls); on a `json.JSONDecodeError` it falls back to
  `json_repair.repair_json(raw_content, return_objects=True)` before giving up.
- `src/nornikel_kg/adapters/llm/settings.py`: `LLMSettings.dataeyes_api_base` default fixed to
  `https://platform.dataeyes.ai/v1` (the previous `api.dataeyes.ai` default pointed at their
  separate Search & Reader product, silently killing the gateway).
- `src/nornikel_kg/services/extraction_service.py`: `ExtractionService` — `_compiled_alias_patterns`
  compiles word-boundary regexes once per instance from `repository.list_alias_index()`:
  digit/Latin-bearing aliases (alloy codes, formulas) match exactly (`(?<!\w)...(?!\w)`);
  pure-Cyrillic aliases longer than 4 chars are stemmed by one char with a bounded
  `\w{0,3}` morphological tail, shorter ones `\w{0,2}` — so «руд» in «оборудование» no longer
  false-hits. `_extract_authors` requires an affiliation signal (`_AFFILIATION_RE`: email/@/
  институт/университет/УДК/orcid/etc.) near the head text; EN initial pairs matching
  `_EN_INITIALS_BLACKLIST` ("po", "us", "uk", ...) are rejected (fixes "P.O. Box"/"U.S.
  Geological" false person-hits); `_AUTHOR_RU_REVERSED_RE` also catches "И.О. Фамилия" order.
  `_document_order_key`/`_LOCATOR_BLOCK_RE`/`_LOCATOR_TABLE_RE` restore document order from the
  stable locator so `_link_publication`'s head-span selection is deterministic, not
  hash-ordered. `_link_publication` extracts `(year, iso_date)` via `domain.dates.extract_date`
  from the head text and writes them into the publication entity's metadata via
  `repository.set_entity_metadata`. LLM extraction now persists typed relations via
  `_write_llm_relations` (endpoints resolved through `EntityResolutionService`, only
  `RELATION_TYPES`-valid relation types are written) in addition to co-occurrence edges;
  `MAX_CO_OCCURRENCE_ENTITIES = 12` still skips co-occurrence generation for spans resolving
  more than 12 entities. `_llm_extract` retries once with a `ValidationError`-feedback prompt
  before recording a `status="rejected"` extraction claim.
- `src/nornikel_kg/services/entity_resolution.py`: `EntityResolutionService.resolve_or_create` —
  resolution ladder now exact key -> alias -> **semantic (new)** -> create. The semantic stage
  (`SemanticMatcherPort`, implemented by `QdrantSemanticMatcher` over the `entities` Qdrant
  collection via `VectorIndexPort.dense_search`) merges at cosine `>= AUTO_MERGE_THRESHOLD =
  0.90` and writes the mention back as a learned alias (`merge_entity_evidence(...,
  new_alias=mention)`); scores in `[REVIEW_THRESHOLD=0.80, 0.90)` are logged only, not merged.
  A digit-veto (`_DIGIT_RE`) and a minimum key length of 4 chars prevent alloy codes/formulas
  from ever merging semantically. Wired only when `ENTITY_SEMANTIC_FALLBACK=true` (default) and
  a retrieval index is configured (`services/runtime.py:get_extraction_service`).
- `src/nornikel_kg/services/graph_service.py`: `GraphService.neighborhood` now applies a
  `type_boost` (`person: 1000`, `publication: 500`, `team: 500`, `laboratory: 500`) when ranking
  neighbors within the limit, so a "who works on topic X" query is no longer crowded out by
  densely-connected `material` nodes.
- `src/nornikel_kg/services/retrieval_service.py`: `RetrievalService` — `index_source(...,
  include_entities: bool = False)` (default off, per-source enrichment no longer re-embeds the
  whole entities collection); `reindex_all()` calls `index_source(..., include_entities=False)`
  per source then indexes entities once via `_index_entities()`. Indexed evidence text is now
  prefixed with the source title (`f"{title}\n{visible_text}"`) so short spans are findable by
  document topic; provenance stays span-exact (only `visible_text` is cited). Optional
  `RerankerPort` (`rerank_candidates: int = 30`): `retrieve_span_ids` over-fetches
  `max(rerank_candidates, top_k)` hits, rejoins/re-filters against DuckDB, then reranks only if
  `len(verified) > top_k`; reranker exceptions degrade to the fused order. New
  `repository.list_evidence_spans_by_ids` performs a targeted rejoin instead of scanning the
  full evidence-span table.
- `src/nornikel_kg/adapters/embeddings/local.py`: `_sparse_model()` reads `SPARSE_LANGUAGE`
  (default `"russian"`) for fastembed's `Bm25` (previously silently defaulted to English
  stemming/stopwords, breaking exact-term sparse matching on Russian text);
  `embed_sparse_query` calls `SparseTextEmbedding.query_embed()` (flat query-term weights) as
  distinct from `embed_sparse` (document weights).
- `src/nornikel_kg/adapters/reranker/cross_encoder.py` (new): `CrossEncoderReranker.rerank` —
  `BAAI/bge-reranker-v2-m3` cross-encoder, ONNX backend by default (`RERANKER_BACKEND=onnx`,
  falls back to `torch` on load failure), `RERANKER_MODEL_ID`/`RERANKER_ENABLED` envs, `max_chars
  = 1600` input cap per candidate.
- `src/nornikel_kg/adapters/gliner_ner/extractor.py`: `sentence_chunks` splits long spans on
  sentence boundaries with one-sentence overlap (`_CHUNK_CHARS = 1500`) instead of a hard
  character cut, and `GLiNERMentionExtractor.extract` dedupes overlapping predictions by global
  `(start, end, entity_type)` offset, keeping the highest-confidence one. Module comment
  documents the evidence-based rejection of GLiNER2 for this project (English-only training,
  `fastino/gliner2-multi-v1` has no `ru` tag, broken relation extraction) — full rationale is in
  `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`.
- `src/nornikel_kg/adapters/ratelimit.py` (new): `RateLimiter`/`get_limiter(name,
  requests_per_second)` — a process-wide, named min-interval limiter registry (one queue per
  named quota); every caller of one provider quota shares one `RateLimiter` instance via
  `get_limiter`. Used by `adapters/embeddings/yandex.py` (`get_limiter("yandex-embeddings",
  YANDEX_EMBED_RPS)`, code default `8`) and `adapters/llm/gateway.py`
  (`get_limiter("llm-completions", LLMSettings.llm_rps)`, code default `5.0`).
- `src/nornikel_kg/adapters/llm/gateway.py`: `LiteLLMGateway.generate_json` now joins the
  `"llm-completions"` rate limiter before every `litellm.completion` call (inside the existing
  `_semaphore` concurrency guard) and retries `litellm.RateLimitError` up to
  `_RATE_LIMIT_RETRIES = 6` times with jittered exponential backoff (`delay` doubles each retry,
  capped at 20s) instead of failing the call on a transient 429 — the folder's LLM quota is
  shared with other consumers. `adapters/llm/settings.py`'s `LLMSettings` gained `llm_rps: float
  = 5.0`; `llm_max_concurrency` default stays `3` in code (the stand raises both via
  `.env.example`: `LLM_RPS=10`, `LLM_MAX_CONCURRENCY=8`, documented Yandex quota of 10 concurrent
  generations). This makes the gateway no longer provider-agnostic-and-unchanged: the retry/pacing
  logic is generic (any provider raising `litellm.RateLimitError` benefits), but it is new code,
  not just an env-level provider switch.
- `src/nornikel_kg/services/qa_service.py`: `DemoQAService` — numeric constraints now go through
  `domain.quantities` (unit-bearing only, canonicalized comparison) via `_apply_numeric_constraints`;
  `_apply_source_scope` for geography/year filters (unchanged contract, still via
  `RunRecorderProtocol.source_metadata()`); `_select_experiments` no longer falls back to an
  arbitrary `experiments[:5]` when no material/property/regime signal matches — an honest empty
  list is returned instead (kept when a material or explicit filter *did* match, matching the
  prior "the scope itself is the query" contract); `_alias_material_tokens` resolves RU material
  codes (e.g. «МН30») through `repository.find_entity`, not string similarity;
  `_CHEMICAL_FORMULA_VETO` (`co2`, `al2o3`-derived tokens, etc.) prevents chemical formulas from
  being misread as unmatched material requests; `_confidence_level(question, selected_experiments,
  summary, selected_evidence)` returns `"high"` only when the question's material/property
  signal actually matched selected experiments; `"medium"` when experiments matched without a
  material/property signal, **or** (added `ef812af`) when no experiments matched but the answer
  is citation-verified and evidence-grounded (`summary and selected_evidence`, the normal case
  on the real corpus — previously indistinguishable from "nothing found" at `"low"`); `"low"`
  only when nothing was found at all; `_conflicts_for_question` only attaches conflicts sharing a
  material/
  experiment/span with the selected evidence (unless the question itself asks about conflicts/
  methods); `_source_context` builds `source_id -> "Title, year, geography"` labels for the
  answer-composer packet (literature-review grouping).
- `src/nornikel_kg/domain/answer_claims.py`: `sentence_numbers_supported` — every number literal
  in an answer sentence must appear in the cited evidence text (decimal-comma tolerant);
  `ClaimVerifier.verify` now also returns `numeric_mismatch_count` in `AnswerVerification`,
  skipping the numeric check for fact-backed sentences (those carrying `supporting_fact_ids`,
  whose numbers come from structured ledger measurements, not literal span text).
- `src/nornikel_kg/services/answer_composer.py`: `LLMAnswerComposer.compose` drops sentences
  whose cited numbers are not supported by the cited evidence text (`sentence_numbers_supported`)
  in addition to the existing citation-existence check; `_packet_prompt` now includes
  `source_context` (year/geography label) per evidence line and an explicit instruction to group
  literature-review answers by year/geography and flag consensus vs disagreement.
  `_ANSWER_SYSTEM_PROMPT` (`24282f1`) additionally instructs the model to synthesize concrete
  values/factors and never refer the reader to table/figure numbers (live bench, 2026-07-04:
  `gpt-oss-120b` synthesized factors best but ran 26-91s, too slow interactively; `aliceai-llm`
  stays the answer model at 6-11s with perfect citation discipline — see
  `mem:TECHDEBT-01-NOW`).
- `src/nornikel_kg/domain/analysis.py`: `_regime_bucket` strips the `reg_`/`regime_` id prefix
  before bucketing by regime type + temperature (previously the raw id put every experiment into
  one bucket, producing fake contradictions between aging and annealing at the same
  temperature); `numeric_disagreement` conflicts now additionally require the same canonical
  unit (`domain.quantities.normalize_unit`) and non-empty, equal measurement methods on both
  sides before comparing values.
- `src/nornikel_kg/services/ingestion_service.py`: `IngestionService` — routes `.xlsx`/`.xls`
  through the lazily-constructed `spreadsheet_parser` (`SpreadsheetDocumentParser`) and `.doc`
  through `legacy_doc_parser` (`LegacyDocParser`); `.docm` is added to `PARSER_EXTENSIONS` and
  goes through the same Docling `DoclingDocumentParser` path as `.pdf`/`.docx`.
  `_apply_source_metadata`/`_set_year_geography` now use `domain.dates.extract_year_from_filename`
  (filename year wins) and `domain.dates.extract_year` (year-marker-guarded) instead of a bare
  `19[5-9]\d|20[0-4]\d` regex; geography's Cyrillic count also folds `ё`.
- `src/nornikel_kg/services/archive_expansion.py` (new): `expand_archives(files, work_dir)` —
  reassembles multipart `X.zip.001`/`.002` splits by byte concatenation (verified against the
  real corpus), extracts plain `.zip` via `zipfile` with a zip-slip guard (`Path(...).is_relative_to`)
  and inner-directory flattening, and extracts `.rar` via `bsdtar` (libarchive) when available,
  else counts `rar_skipped`. `INGESTIBLE_EXTENSIONS` gates which extracted members are kept.
- `src/nornikel_kg/adapters/spreadsheet/parser.py` (new): `SpreadsheetDocumentParser.parse` —
  `pandas.read_excel(..., sheet_name=None, header=None, dtype=str)`, caps `MAX_SHEETS = 20`,
  `MAX_ROWS_PER_SHEET = 300`, `MAX_COLUMNS = 30`; truncated row counts are recorded in
  `metadata["truncated_rows"]`, not silently dropped; each non-empty sheet becomes a
  `ParsedTable`.
- `src/nornikel_kg/adapters/legacy_doc/parser.py` (new): `LegacyDocParser.parse` — shells out to
  `antiword` then `catdoc -w` (first available, first non-empty stdout wins); raises
  `ParserError` (same quarantine contract as `NoTextLayerError`) when neither binary is
  installed or the extracted text is empty.
- `src/nornikel_kg/adapters/docling/parser.py`: `.docm` added to `_SUPPORTED_EXTENSIONS`; the
  `DocumentStream` name is rewritten to a `.docx` stem so Docling's format detection stays on
  the DOCX path (macros are ignored, not executed).
- `src/nornikel_kg/adapters/duckdb/repositories.py`: `set_entity_metadata(entity_id, updates)`
  merges keys into `entities.metadata_json`; `list_evidence_spans_by_ids(span_ids)` for targeted
  retrieval rejoin; `_delete_source_records` now cascades into `relations`/`entities` (stripping
  the deleted span IDs from `evidence_span_ids_json`, deleting rows that empty out — except
  dictionary-seeded entities, whose IDs don't start with `ent_`), `extraction_claims`, and
  `ingestion_runs`; `list_sources()`/`SourceSummary` now also return `year`/`geography`.
- `services/api/routes/sources.py`: `DELETE /sources/{id}` now also best-effort deletes the
  source's Qdrant units (`retrieval.index.delete_source_units`, wrapped in
  `contextlib.suppress(Exception)`); upload accepts `.docm`/`.doc`/`.xlsx`/`.xls` in addition to
  the prior extension set, each with its own MIME allow-list.
- `services/api/routes/graph.py`: `GET /graph/timeline` now also includes `publication` entities
  that carry a `year` or `date` in their metadata (undated publications are excluded to avoid
  noise); events sort by `date` then `year`. `GET /graph/demo-path` raises `404` instead of
  indexing into an empty `graph_paths` list when the ledger has no matching demo path.
- `apps/web/src/`: `AnalysisWorkbench.tsx` polls `refreshSources` every 4s while any source is
  `"running"`, shows a confidence badge, and renders a "Противоречия в данных" conflicts panel
  when `answer.conflicts` is non-empty; `ArtifactBankPanel.tsx` accepts the new upload extensions
  and shows `year`/`geography` chips on source cards; `DecisionsTimeline.tsx` falls back to
  `event.year` when `event.date` is null; `shared/api/types.ts`'s `SourceSummary` gained
  `year`/`geography`, `AskResponse.verification` gained `numeric_mismatch_count`, and
  `TimelineEvent` gained `year`.
- `src/nornikel_kg/adapters/embeddings/yandex.py` (new): `YandexEmbeddingBackend` — dense
  1536-dim embeddings via the canonical `https://ai.api.cloud.yandex.net/foundationModels/v1/
  textEmbedding` host (the old `llm.api` host still answers but is the legacy alias, per the
  module docstring), `x-folder-id` header, 4000-char input truncation (documented 2048-token
  cap), 7 retries with exponential backoff + jitter (`_MAX_RETRIES = 7`). A shared
  `adapters.ratelimit.RateLimiter` (obtained via `get_limiter("yandex-embeddings",
  YANDEX_EMBED_RPS)`, code default `8`, `.env.example` stand value `9.5`) paces requests below
  the shared 10 RPS folder quota — retry-with-backoff alone loses against a saturated quota when
  many enrichment threads fire concurrently (observed live as a 429 storm).
  `embed_dense`/`embed_dense_query` use separate doc/query model URIs
  (`YANDEX_EMBED_DOC_MODEL`/`YANDEX_EMBED_QUERY_MODEL`, both default `text-embeddings/latest`);
  a module-level query cache (`_query_cache`, `_QUERY_CACHE_MAX = 256`) spares repeat demo
  questions. `embed_sparse`/`embed_sparse_query` delegate to `LocalEmbeddingBackend` (BM25 stays
  local). Wired via `EMBEDDING_BACKEND=yandex` in `services/runtime.py`.
- `src/nornikel_kg/ports/retrieval.py`: `EmbeddingBackendPort` gained `embed_dense_query(texts) ->
  list[list[float]]` (distinct from `embed_dense`, may use a separate query-side model),
  implemented by `local.py`/`fake.py`/`yandex.py`; `QdrantVectorIndex.hybrid_search`/
  `dense_search` call `embed_dense_query` for the query vector.
- `src/nornikel_kg/adapters/qdrant_index/index.py`: `QdrantVectorIndex.index_units(collection,
  units, *, skip_unchanged: bool = True)` is incremental — every point payload carries a
  `text_hash` (`hashlib.blake2s`, 16-byte digest); when `skip_unchanged` and the collection
  exists, units whose stored hash matches the current text are dropped from the pending batch
  before ever calling the embedding API. `_UPSERT_BATCH = 128` batches `client.upsert` calls (a
  single ~1700-point x 1536-dim upsert exceeded Qdrant's request-size limit, observed live as a
  400). New `prune_source_units(collection, source_id, keep_unit_ids)` scrolls a source's points
  and deletes those not in `keep_unit_ids` (stale points from a re-parse), called after indexing,
  never before (a failed re-embed must not lose existing vectors).
- `src/nornikel_kg/services/retrieval_service.py`: `RetrievalService.index_source` calls
  `index_units` (incremental) then `prune_source_units` when the index supports it;
  `reindex_all()` logs `"Reindex complete: %d units"` via `logger.info` as an ops-greppable
  completion marker (deploy tooling greps this exact line rather than relying on a
  points-count heuristic). `EVIDENCE_COLLECTION = os.getenv("QDRANT_COLLECTION",
  "evidence_units")`; `ENTITY_COLLECTION = os.getenv("QDRANT_ENTITY_COLLECTION",
  f"{EVIDENCE_COLLECTION}_entities")` — deriving the entity collection name from the evidence
  collection means switching `QDRANT_COLLECTION` for a new embedder never queries
  stale-dimension vectors from an old entity collection.
- `src/nornikel_kg/adapters/duckdb/repositories.py`: `DuckDBLedgerRepository` gained a
  `_data_version` int counter (incremented in `ingest_source_bytes`/`ingest_parsed_document`/
  `_delete_source_records`/`set_source_metadata`, i.e. every ledger-mutating write path) and a
  public `data_version` property.
- `src/nornikel_kg/services/qa_service.py`: `DemoQAService._load_packet` caches the loaded
  `EvidenceLedgerPacket` as `self._packet_cache: tuple[int, EvidenceLedgerPacket] | None`, keyed
  by `ledger_repository.data_version`; a cache hit skips `load_demo_packet()` (a full
  evidence/experiment scan that previously dominated `ask` latency), invalidated automatically
  whenever any write bumps `_data_version`.
- `src/nornikel_kg/services/ingestion_service.py`: `IngestionService._schedule_enrichment`'s
  inner `enrich()` closure now wraps its entire body in `try/except Exception`, logging
  `logger.exception` and recording `status="failed"` on any error (previously an unhandled error
  inside the daemon thread — e.g. the missing-`tenacity` case below — silently killed the thread
  and stranded the run's status at `"running"` forever).
- `pyproject.toml`: `tenacity>=8.2.0` is now a hard main dependency — `litellm`'s `num_retries`
  retry path imports `tenacity` lazily and raises a bare `Exception` when it is absent, which
  killed enrichment threads live before this fix.
- `services/api/main.py`: sets `logging.getLogger("nornikel_kg").setLevel(logging.INFO)` and
  calls `logging.basicConfig(level=logging.INFO)` when the root logger has no handlers, so
  reindex-completion and enrichment-failure INFO/ERROR logs are visible in the running container.
- `apps/web/src/pages/`: six-section SPA — `workbench/` (search, ex-`AnalysisWorkbench` slimmed
  to an `injectedQuestion?: string | null` prop), `graph/`, `data/`, `analytics/`, `eval/`,
  `security/`; `WorkbenchPage.tsx` renders the nav (`Поиск`/`Граф знаний`/`Данные`/`Аналитика`/
  `Качество`/`Безопасность`). `ArtifactBankPanel.tsx` gained an optional
  `onEnrich?: (sourceId: string) => Promise<void>` prop.
- `services/api/routes/stats.py` (new): `GET /stats/overview` returns
  `get_ledger_repository().corpus_stats()`; `GET /stats/answer-runs?limit=` (1-100, default 20)
  returns `{"runs": get_ledger_repository().list_answer_runs(limit)}`.

## Current Behavior

**Provenance note (verified 2026-07-04)**: this repo's `main` is a freshly squashed
history after the 2026-07-03 migration to `hack-2026-nornikel` (see
`mem:CORE-01-INDEX`'s Repository Identity And History section). Commit SHAs cited below
(e.g. `7c5d30b`, `210bddd`, `98fc57e`, `67d3bca`, `327f47c`, `6feff7a`, `9338017`) predate
that squash and are not ancestors of the current `HEAD`; they identify commits on the
archived `nornikel-kg-search` line only. The architecture/behavior they describe was
re-verified directly against the working tree in this sync pass.

P0 scaffold uses React 19/Vite 8/TypeScript, FastAPI, Python 3.12, and DuckDB as the evidence
ledger and graph store of record. Runtime wiring (`src/nornikel_kg/services/runtime.py`) lazily
builds every service behind `@lru_cache` singletons: `get_ledger_repository`, `get_qa_service`,
`get_retrieval_service` (`EMBEDDING_BACKEND=off|local|fake|yandex`, plus `RERANKER_ENABLED` wiring a
`CrossEncoderReranker` into `RetrievalService`), `get_ingestion_service`, `get_extraction_service`
(`GLINER_ENABLED` default `true`, `LLM_EXTRACTION_ENABLED` default `false`, and
`ENTITY_SEMANTIC_FALLBACK` default `true` — wires a `QdrantSemanticMatcher` into
`EntityResolutionService` only when a retrieval index exists), and `get_graph_service`.

Docling, GLiNER, sentence-transformers, fastembed, pandas, and antiword/catdoc/bsdtar
subprocesses are all invoked lazily inside their adapter modules (never at import time), so the
core API/tests do not require the `ingest` optional dependency group unless those code paths
execute.

## Contracts And Data

Implemented ports: `EvidenceLedgerPort`, `LLMPort`, `DocumentParserPort`/`UrlFetcherPort`,
`EmbeddingBackendPort`/`VectorIndexPort` (now including `embed_sparse_query`/`dense_search`).

`domain/extraction.py` defines `ENTITY_TYPES` (material, regime, property, equipment, team,
person, laboratory, conclusion, decision, value, **publication**) and `RELATION_TYPES` (MADE_OF,
APPLIES_REGIME, HAS_MEASUREMENT, OF_PROPERTY, PRODUCED_EFFECT, USED_EQUIPMENT, PERFORMED_BY,
AUTHORED_BY, SUPPORTED_BY, FROM_DOCUMENT, DERIVED_FROM, CONTRADICTS, CONCLUDES,
**DESCRIBED_IN**) — both vocabularies now cover the publication/author graph that
`ExtractionService._link_publication` writes, and `EXTRACTION_JSON_SCHEMA` is strict-valid for
guided-JSON LLM extraction (see Entry Points). Co-occurrence relations wired in
`ExtractionService`: material->USED_EQUIPMENT (equipment), material->PERFORMED_BY (team),
material->HAS_MEASUREMENT (property), material->APPLIES_REGIME (regime),
material->CONCLUDES (decision/conclusion); LLM-typed relations are persisted separately via
`_write_llm_relations` when both endpoints resolve to entities.

`domain/models.py`'s `AskFilters` carries `geography: list[str]`, `year_from`/`year_to`,
alongside the existing filter fields (unchanged from the prior sync).

Concrete P0 domain services: `EvidenceSpanFactory`, normalization helpers in
`domain/normalization.py`, `domain/quantities.py`, `domain/dates.py`, `ConflictDetector`,
`GapAnalyzer`, `ClaimVerifier`, and `DemoQAService` as the answer assembler.

## Invariants

- Domain logic depends on ports, not vendor clients.
- React must call FastAPI contracts and must not bypass application services.
- If DuckDB and Qdrant disagree, DuckDB wins; Qdrant hits are always rejoined and re-filtered
  against DuckDB before being trusted.
- Only `src/nornikel_kg/adapters/llm/gateway.py` may `import litellm`.
- Extraction and answer-composer system prompts explicitly instruct the model that fragment
  text is data, not instructions (see `mem:SEC-01-ACL-AND-PROMPT-INJECTION`).
- Parser/network/extraction/retrieval failures degrade gracefully and never surface as an
  unhandled 500 or an unverified answer.
- Every answer sentence's cited numbers must literally appear in the cited evidence text, unless
  the sentence is fact-backed (`supporting_fact_ids` present).
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()` — the connection
  is persistent per repository instance behind a class `RLock` (`mem:DATA-01-EVIDENCE-LEDGER`).

## Change Rules

Keep implementation changes aligned with `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md` (current
wave plan) first, then update ADRs if a stack boundary changes.

## Verification

- `make ci`: backend/frontend gate; `uv run pytest` verified 151 passed / 5 skipped at `652317e`
  (live-run verified in this sync pass); `ruff`/`mypy` both clean (live-run verified, mypy: "no
  issues found in 76 source files").
- `make eval`: deterministic + retrieval-augmented evidence packet verification (17 questions,
  synthetic corpus only, incl. adversarial prompt-injection cases).
- `docker compose config`: validates server-first Compose wiring (`api`, `web`, `qdrant`).

<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 8d10cc4 chore: untrack the 56MB design reference package
Scope: apps/web/; services/api/; src/nornikel_kg/; docker-compose.yml; .github/workflows/ci.yml; src/nornikel_kg/domain/encoding.py; src/nornikel_kg/domain/table_facts.py;
  src/nornikel_kg/domain/geography.py; src/nornikel_kg/services/archive_expansion.py;
  src/nornikel_kg/adapters/trafilatura/fetcher.py; services/api/routes/health.py;
  services/api/routes/graph.py
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
  (`MIN_YEAR=1950`, `MAX_YEAR=2027`). `parse_time_scope(question, *, now_year) ->
  tuple[int | None, int | None]` (new, commit `4ede8c5`) turns explicit natural-language
  temporal phrasings in a *question* into `(year_from, year_to)`: `_YEAR_RANGE_RE`
  (`YYYY-YYYY`/`YYYY–YYYY`, optional «гг.»/«года»), `_LAST_N_YEARS_RE` («за последние N
  лет» / «last N years», 1-50), `_LAST_YEAR_RE` («за последний год»), `_SINCE_YEAR_RE`
  (RU «с»/«начиная с»/EN `after`/`since` + year), `_UNTIL_YEAR_RE` (RU «до»/«по»/EN
  `before`/`until` + year). The RU since/until patterns **require** a trailing «г.»/«год…»
  marker — without it, «нагрев до 2000 градусов» or «раствор с 2019 мг/л» never parse as a
  scope (verified: `tests/unit/test_dates.py::test_parse_time_scope_requires_year_marker`).
  A bare year mention with no explicit temporal phrasing (e.g. «проба 2020») is never
  returned as a scope — same "fact, not filter" contract as `extract_year`
  (`tests/unit/test_dates.py::test_parse_time_scope_last_n_years`).
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
- `src/nornikel_kg/services/qa_service.py`: `EvidenceQAService.ask` (commit `4ede8c5`) now calls
  `_effective_filters(request)` first: explicit `request.filters.year_from`/`year_to` win, but
  when they are unset, `domain.dates.parse_time_scope(request.question, now_year=date.today()
  .year)` fills them in from the question text (e.g. «за последние 5 лет»), via
  `AskFilters.model_copy(update={...})`. A question-derived scope is **permissive**
  (`keep_unknown_year=True`): sources with no recorded year are kept, since not knowing the
  year is not the same as being out of range; an explicit UI/API year filter stays **strict**
  (`keep_unknown_year=False`, computed as `strict_years = request.filters is not None and
  (request.filters.year_from is not None or request.filters.year_to is not None)`). The shared
  predicate `_scope_predicate(filters, metadata, *, keep_unknown_year)` (new) implements this
  once and is used by both `_apply_source_scope` (experiment table, extended with a
  `keep_unknown_year` kwarg) and the new `_apply_scope_to_evidence(evidence, filters, *,
  keep_unknown_year)` — the latter means `EvidenceQAService.ask` now also filters the evidence
  packet passed to answer synthesis by year/geography scope, not only the experiment table
  (previously an out-of-scope evidence span could still leak into the LLM packet even though
  its experiment was filtered out). `_confidence_level`/run-recording now read the
  scope-enriched `filters` (renamed local variable), not the raw `request.filters`, so
  `record_answer_run`'s persisted `filters` reflect the effective (explicit-or-derived) scope.
  Verified: `tests/unit/test_answer_honesty.py::test_question_time_scope_keeps_unknown_year_sources`
  (derived scope keeps a year-less fixture source; an explicit `AskFilters(year_from=2021)`
  drops it) and `scripts/run_eval.py`'s `q_year_phrase_is_not_a_filter` («... до 2020 года?»)
  now passes via this permissive derived-scope path (the question's «до 2020 года» phrase is
  parsed as an explicit `year_to=2020` scope, but the fixture's year-less Ni-30Cu experiment is
  still kept — live-run verified in this sync pass, `experiment_count: 1`).
  Numeric constraints go through
  `domain.quantities` (unit-bearing only, canonicalized comparison) via `_apply_numeric_constraints`;
  `_select_experiments` no longer falls back to an
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
  was the answer model at that point, 6-11s with perfect citation discipline). **Answer model
  changed same day (`f72c7f6`, verified in `.claude/CLAUDE.md`/`.env.example` at `HEAD`)**: the
  stand now answers on `deepseek-v4-flash` (owner requirement) — `json_repair` recovers its
  non-native JSON through the real gateway, 4/4 verified, citation 1.0, zero numeric
  fabrication, richer detail, ~17s warm (`LLM_TIMEOUT_S=60`). **Extraction moved to
  `deepseek-v4-flash` too, same day (`42ca7ba`, verified in `.claude/CLAUDE.md`/`.env.example`
  at `HEAD`)**: isolation bench reported 0/6 JSON failures and more relations/span than
  `aliceai-llm`, at ~16s/span (2.4x slower); the corpus graph was rebuilt clean on DeepSeek —
  see `mem:DATA-01-EVIDENCE-LEDGER`'s "Corpus Graph Rebuilt On DeepSeek" section for the
  entity/relation counts. `aliceai-llm` (native strict-JSON, 2.4s) stays available as a fast
  fallback model in the catalog, not the active extraction path.
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
- `src/nornikel_kg/services/qa_service.py`: `EvidenceQAService._load_packet` caches the loaded
  `EvidenceLedgerPacket` as `self._packet_cache: tuple[int, EvidenceLedgerPacket] | None`, keyed
  by `ledger_repository.data_version`; a cache hit skips `load_evidence_packet()` (a full
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
- `apps/web/src/pages/`: at PR #18 this was a six-section state-nav SPA anchored by
  `workbench/`'s `WorkbenchPage.tsx`. **Superseded by the 2026-07-04 frontend redesign** (see the
  dated section below) — `workbench/` was deleted, its search view now lives at `pages/search/`,
  and the top-level nav moved into `widgets/app-layout/`. `ArtifactBankPanel.tsx` gained an
  optional `onEnrich?: (sourceId: string) => Promise<void>` prop (unaffected by the redesign).
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
`GapAnalyzer`, `ClaimVerifier`, and `EvidenceQAService` as the answer assembler.

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

- `make ci`: backend/frontend gate; `uv run pytest` verified 182 passed / 5 skipped at `ee84a6b`
  (live-run verified in this sync pass, up from 154 passed / 5 skipped at `4ede8c5`); `ruff`
  ("All checks passed!") and `mypy` ("Success: no issues found in 79 source files") both clean
  (live-run verified in this sync pass).

## Wave 10 — Real-Corpus Audit Response Modules (2026-07-04, HEAD `ee84a6b`)

See `mem:CORE-01-INDEX`'s "Wave 10" section for the full commit-by-commit narrative
(`a2a8908`..`ee84a6b`, plan `.serena/plans/10_AUDIT_RESPONSE_PLAN.md`). Module-level additions
verified against the working tree at `HEAD`:

- `src/nornikel_kg/domain/encoding.py` (new): `decode_text_bytes(content) -> tuple[str, str]`
  cascades `utf-8-sig` -> `utf-8` -> `cp1251`, then `charset_normalizer.from_bytes`, then a lossy
  UTF-8 replace; wired into CSV parsing so CP1251-encoded real-corpus CSVs no longer fail ingest.
- `src/nornikel_kg/domain/table_facts.py` (new): `extract_facts_from_row(headers, values) ->
  list[NumericFact]` (`NumericFact` carries `subject`/`subject_label`/`prop`/`value`/`unit`)
  reads header role hints (`_SUBJECT_HEADER_HINTS`/`_VALUE_HEADER_HINTS`/`_UNIT_HEADER_HINTS`)
  to turn a headered row into subject-tagged numeric facts, handling both wide
  (unit-in-header) and tall (subject-column + value-column) table layouts; unit parsing
  delegates to `domain/quantities.py:normalize_unit` so `мг/дм³` and `мг/л` compare equal.
- `src/nornikel_kg/ports/parser.py`: `ParsedTable`/`ParsedTableRow`/`ParsedTableCell` gained a
  `header` field; `adapters/spreadsheet/parser.py` and `adapters/docling/parser.py` populate it,
  and a row's `.text` becomes header-labeled (e.g. "Сульфаты, мг/л: 300") instead of a bare
  value list.
- `src/nornikel_kg/domain/quantities.py`: `NumericConstraint` gained `subject: str = ""`
  (canonical subject token, `""` = applies to any subject); `parse_parameter_constraints`
  segments a question at each numeric-bound clause and binds it to the analyte/parameter
  subject(s) named since the previous bound (`_subjects_before`), falling back to a subjectless
  constraint when no subject is resolvable; `facts_satisfy_constraints(constraints, facts)`
  matches a subject-bound constraint only against same-subject same-unit facts, a subjectless
  one against unit-only.
- `src/nornikel_kg/services/qa_service.py`: `EvidenceQAService._drop_constraint_violating_evidence`
  (new, called from `ask`) removes evidence spans whose own extracted facts violate a bound
  numeric constraint, so a multi-analyte question (e.g. sulfates/chlorides/Ca/Mg/Na ranges)
  gets an honest, constraint-consistent evidence set instead of citing out-of-range spans.
- `src/nornikel_kg/domain/extraction.py`: `ENTITY_TYPES`/`RELATION_TYPES` extended with case
  vocabulary (`process`, `condition`, `facility`, `experiment`, `method`, `expert`,
  `organization`, `location`, `technology_solution`, `economic_indicator`, `recommendation`,
  `limitation`, `patent`, `standard` entity types; `USES_MATERIAL`, `OPERATES_AT_CONDITION`,
  `HAS_ECONOMIC_INDICATOR`, `PRODUCES_OUTPUT`, `SHOWS_EFFECT`, `EXPERT_IN`, `MEMBER_OF`,
  `VALIDATED_BY`, `HAS_LIMITATION`, `RECOMMENDED_FOR`, `SIMILAR_TO` relation types); the
  extraction prompt was updated to describe the expanded vocabulary.
- `src/nornikel_kg/services/archive_expansion.py`: `expand_archives` now preserves each member's
  inner directory path and writes to a collision-free target (previously flattened to
  basenames and could silently overwrite same-named files across year-partitioned corpus
  directories); the zip-slip guard (`Path(...).is_relative_to`) is unchanged.
- `src/nornikel_kg/adapters/trafilatura/fetcher.py`: `assert_public_url(url)` (new) rejects
  non-`http`/`https` schemes and private/loopback/link-local/reserved/metadata-address hosts;
  called from `fetch()` before any network request, guarding `POST /sources/import-url` against
  SSRF.
- `src/nornikel_kg/domain/geography.py` (new): `detect_geography(head_text) -> str | None`
  returns `"ru"`/`"foreign"`/`"mixed"`/`None` from explicit RU/foreign country-organization-
  location signal word lists (`_RU_SIGNALS`/`_FOREIGN_SIGNALS`), falling back to the
  Cyrillic-vs-Latin script ratio only when neither side names a location and there is enough
  text (`> 40` combined letters); `IngestionService` now calls this instead of the prior
  pure-script heuristic.
- `services/api/routes/health.py`: `GET /health` now returns `llm_enabled`, `answer_model`/
  `extraction_model` (derived from `LLM_ANSWER_MODEL`/`LLM_EXTRACTION_MODEL` env URIs via
  `_model_label`, or `"off"` when `LLM_ENABLED` is false), and `embedding_backend`
  (`EMBEDDING_BACKEND` env, default `"off"`).
- `services/api/routes/graph.py`: the orphaned `GET /graph/demo-path` route was removed
  (verified absent at `HEAD`).
- `apps/web/src/shared/api/types.ts`: `EvidenceSpan` gained `locator: Record<string, unknown>`.
  `apps/web/src/widgets/analysis-workbench/ui/AnalysisWorkbench.tsx` assigns each cited span a
  stable per-answer citation number (`citationIndex`, first-appearance order) and renders a
  numbered `citation-chip` plus a `citation-verified` badge per answer sentence; clicking a chip
  scrolls to and highlights the corresponding evidence card. `apps/web/src/widgets/
  artifact-bank/ui/EvidenceList.tsx` and `apps/web/src/shared/config/theme/theme.css` carry the
  supporting markup/styles. The live `health.answer_model` (or `"детерминированный режим"` when
  `llm_enabled` is false) is now rendered by `apps/web/src/widgets/app-layout/ui/Header.tsx`
  (`WorkbenchPage.tsx`, which did this previously, was deleted in the 2026-07-04 redesign — see
  below). `apps/web/src/pages/data/ui/DataPage.tsx` renders
  `stats.quarantine_reasons` (see `mem:DATA-01-EVIDENCE-LEDGER`).
- `make eval`: deterministic + retrieval-augmented evidence packet verification (17 questions,
  synthetic corpus only, incl. adversarial prompt-injection cases).
- `docker compose config`: validates server-first Compose wiring (`api`, `web`, `qdrant`).

## Frontend Redesign — react-router Multi-Page App (2026-07-04, HEAD `e7b4d51`)

Three commits (`6eca379` feat: design-token overhaul + header/footer shell + landing + routing,
`f91b90c` feat: jury demo cockpit, `c468df8` feat: question-first search layout) replaced the
state-nav SPA with a `react-router-dom` v7 (`apps/web/package.json:"react-router-dom": "^7.18.1"`)
multi-page app, followed by `d644575` (docs note) and `8d10cc4` (untrack the 56MB mockup
package). A follow-up mockup-fidelity wave then landed four commits — `fb5c591` (experts/labs
directory on real graph entities + new `/entities/by-type` API), `4b8f014` (section hero
illustrations + comparison verdict matrix), `20e5d67` (framed hero illustrations, RU graph
labels, token-aligned node colors), `e7b4d51` (landing capability grid) — which upgraded the
ExpertsPage/ComparePage from static explainers to data-backed views (see the updated bullets and
the "Mockup-fidelity wave" subsection below). Verified against the working tree at `HEAD`:

- `apps/web/src/app/ui/App.tsx`: `BrowserRouter` + `Routes` define one `Route` tree under a shared
  `AppLayout` element — `index` -> `LandingPage`, `search` -> `SearchPage`, `graph`/`data`/
  `analytics`/`eval`/`security` -> route wrapper components (`GraphRoute`/`DataRoute`/
  `AnalyticsRoute`/`EvalRoute`/`SecurityRoute`) that each render a `PageHero` plus the section page,
  `compare` -> `ComparePage`, `experts` -> `ExpertsPage`, `demo` -> `DemoPage`, and a catch-all
  `path="*"` that `Navigate replace to="/"`. `AnalyticsRoute` wires `AnalyticsPage`'s
  `onGapQuery` to `navigate(\`/search?q=${encodeURIComponent(question)}\`)`.
- `apps/web/src/widgets/app-layout/` (new): `AppLayout.tsx` renders `Header` + `<main
  className="site-main"><Outlet /></main>` + `Footer`. `Header.tsx` renders the brand link (logo
  `/brand/logo.png` + "Научный клубок"), a "Команда: Попугайчики" badge, a `NavLink` row built
  from `shared/config/nav.ts`'s `NAV_ITEMS`, a "Норникель Hackathon" badge whose `title` shows the
  live model (`fetchHealth()` -> `health.llm_enabled ? health.answer_model :
  "детерминированный режим"`, falls back to `"Yandex AI Studio"` before the fetch resolves), and a
  mobile menu toggle. `Footer.tsx` renders a global "Смотреть демо" CTA linking to `/demo`. The old
  `apps/web/src/pages/workbench/` (`WorkbenchPage.tsx`, sidebar-nav SPA shell) was deleted.
- `apps/web/src/shared/config/nav.ts` (new): `NAV_ITEMS` lists eight entries — `/search`
  (Поиск), `/graph` (Граф знаний), `/data` (Данные), `/analytics` (Аналитика), `/compare`
  (Сравнение), `/experts` (Эксперты), `/eval` (Качество), `/demo` (Демо). **`/security` is not in
  `NAV_ITEMS`** — verified by grep, the route and `SecurityPage` still exist and are linked from
  `pages/demo/ui/DemoPage.tsx`'s `SECTIONS` list and reachable by direct URL, but the header/mobile
  nav omits it (known gap, see `mem:TECHDEBT-01-NOW`). The same file also exports `ENTITY_COLORS`/
  `entityColor(entityType)`, a shared entity-type -> CSS-variable-name map used by graph-node
  coloring.
- `apps/web/src/shared/config/theme/theme.css` (rebuilt, now 1889 lines): blue primary
  (`--color-brand: #2563eb`, `--color-brand-strong: #1d4ed8`, `--color-brand-deep: #1e3a8a`,
  `--color-brand-soft: #dbeafe`) plus teal/violet accents; entity-type color tokens
  (`--entity-material: #0d9488`, `--entity-process: #2563eb`, `--entity-equipment: #0ea5e9`,
  `--entity-experiment: #7c3aed`, `--entity-publication: #059669`, `--entity-expert: #2563eb`,
  `--entity-conclusion: #7c3aed`) backing `nav.ts`'s `ENTITY_COLORS`; `Inter` is the primary font
  family; new CSS blocks style the header/footer shell, `page-hero`, landing, demo cockpit, and the
  collapsible search filters.
- `apps/web/src/pages/landing/ui/LandingPage.tsx` (new, route `/`): hero section (title + CTA
  links to `/demo` and `/search` + `hero-graph.png`), a `heroStats` row sourced from
  `fetchStats()` (`stats.evidence_spans`, `stats.sources`, a static "0 неподтверждённых чисел"
  metric, and a static "RU / зарубеж" geography label), a 4-item feature-card grid, and a 3-step
  "как это работает" section.
- `apps/web/src/pages/demo/ui/DemoPage.tsx` (new, route `/demo`, "jury cockpit"): on mount calls
  `fetchStats()`, `fetchEvalSummary()`, and `askQuestion(JURY_QUESTION)` (a hardcoded
  precious-metals-in-matte/slag question); renders a left KPI column (sources, citation coverage,
  answer accuracy) and a right KPI column (quarantined files, conflict count, expert count, a
  static "≈ 7 сек" latency label gated on `answer.run_id`), a live-answer result card
  (`answer.answer_summary`, source chips from `answer.evidence`), a 5-card section-preview grid
  (`/search`, `/graph`, `/data`, `/analytics`, `/security` — this is the only header-less place
  `/security` is linked), a problem->solution->value 3-step section, and a closing banner.
- `apps/web/src/pages/experts/ui/ExpertsPage.tsx` (route `/experts`, rebuilt in `fb5c591` to be
  data-backed): on mount calls `fetchStats()` plus three `fetchEntitiesByType(...)` requests
  (`"person,expert"` limit 12, `"laboratory,facility"` limit 8, `"organization,team"` limit 8)
  against the new `/entities/by-type` endpoint. Renders a hero + `mascot-span.png` card, four
  stat cards, a ranked "Кого спросить" list built from the real person/expert entities (each row
  shows `initials()`-derived avatar + `evidence_count`), a lab-card grid, and a topic-chip row —
  no more hardcoded expert names.
- `apps/web/src/pages/compare/ui/ComparePage.tsx` (route `/compare`, rebuilt in `4b8f014`): a
  verdict-matrix comparison table. A `Verdict` union (`"strong" | "medium" | "needs_data"`) drives
  a `VerdictCell` (подтверждено / частично / нет данных) rendered across `ROWS` (6 metrics:
  извлечение, CAPEX/OPEX, энергозатраты, холодный климат, экология, доказательность) ×
  `COLUMNS` (Биоокисление / Гипербарическое выщелачивание / Флотационные реагенты), with a legend,
  an `an-compare.png` `PageHero` aside, and a `Link` that pre-fills a comparison question into
  `/search?q=...`. Still illustrative structure — no dedicated comparison-table endpoint exists;
  live comparisons are produced by the general answer pipeline.
- `apps/web/src/shared/ui/PageHero.tsx` (new): `eyebrow`/`title`/`caption` props, used by the
  `App.tsx` route wrapper components and `ExpertsPage`/`ComparePage`.
- `apps/web/src/widgets/analysis-workbench/ui/AnalysisWorkbench.tsx` reordered to question-first:
  `QuestionForm` (from `@/features/ask-question`) renders first, and the material/process/
  condition/geography/year filters plus the source-selection list now collapse into a
  `<details className="filters-details"><summary>Фильтры: ...</summary>...</details>` block below
  it (previously the 49-item source checklist rendered before the question box).
- Brand assets: `apps/web/public/brand/` (12MB total, 30 files per `ls | wc -l`) — the original
  eight (`logo.png`, `mascot.png`, `mascot-checks.png`, `mascot-span.png`, `hero-graph.png`,
  `arctic-bg.png`, `evidence-shield.png`, `team-badge.png`) plus the mockup asset set: product
  illustrations `feat-*.png` (search/ingest/path/security/…) used as framed `PageHero` asides, and
  analytics illustrations `an-*.png` (`an-geo`, `an-heatmap`, `an-quality`, `an-compare`, …).
  ~14 are wired into pages, the rest are available. `apps/web/index.html`'s `<title>` is "Научный
  клубок — единая карта знаний R&D" with matching `og:title`/`og:description`/`og:image`
  (`/brand/hero-graph.png`).
- `nauchny_klubok_site_package/` (the 56MB mockup/reference package the redesign was built from)
  was added to `.gitignore` in `8d10cc4` after an earlier `git add -A` had tracked it; it stays on
  disk but is no longer part of the tracked tree or the web build context.
- Gates: `cd apps/web && npm run typecheck` (`tsc --noEmit`) and `npm run build` both pass clean
  (typecheck re-run clean in this sync pass); the live stand `https://nornikel.nddev.asia` serves
  `/` and `/demo` (SPA fallback, per `.claude/CLAUDE.md`).

### Mockup-fidelity wave (`fb5c591`..`e7b4d51`, 2026-07-04)

- **New API contract `GET /entities/by-type`** (`services/api/routes/entities.py:19`,
  `entities_by_type`): query params `entity_type` (`str`, comma-separated types, 1..200 chars) and
  `limit` (`int`, default 24, 1..100); splits `entity_type` on commas and returns
  `{"entities": [...]}`. **Declared before the `/{entity_id}` catch-all** so the literal path is not
  swallowed by the dynamic route — order matters, keep `by-type` above `{entity_id}`.
- Backed by `AdapterLedgerRepository.list_entities_by_type(entity_types, limit=24)`
  (`src/nornikel_kg/adapters/duckdb/repositories.py:897`): returns entities of the given type(s)
  **most-referenced first**, using `evidence_count` (length of `evidence_span_ids_json`) as a
  prominence proxy; empty `entity_types` returns `[]`. Powers the experts/labs directory.
- Client: `fetchEntitiesByType(entityType, limit=24)` + `TypedEntity`
  (`{entity_id, entity_type, canonical_name, evidence_count}`) in `apps/web/src/shared/api/`
  (`client.ts`, `types.ts`, re-exported from `index.ts`).
- Landing capability grid (`e7b4d51`): a fourth landing section (`.capability-grid`, 4 cards) —
  «География» (`an-geo.png`), «Диапазоны и условия» (a `mini-kv` static range table), «Команды и
  эксперты», «Актуализация знаний» (a static 92% `freshness` bar). All illustrative copy, no new
  data fetch.
- Section hero illustrations (`4b8f014`/`20e5d67`): the `PageHero` `aside` slot now carries a
  framed `.page-hero-illus` `<img>` (white rounded frame — `border` + `border-radius` +
  `box-shadow` — added because the product screenshots have white backgrounds that otherwise blend
  into white hero cards) across search/graph/data/analytics/compare/security sections.
- Graph labels/colors (`20e5d67`): `GraphPage.tsx`'s `TYPE_LABELS` extended with Russian labels
  for the full R&D ontology (process/regime/condition/facility/organization/location/
  technology_solution/economic_indicator/…); `GraphNeighborhood.tsx`'s `TYPE_COLORS` aligned to the
  entity-color tokens in `theme.css`/`nav.ts`.
- Gates after the wave: `tsc --noEmit`, `npm run build`, `uv run mypy`, `uv run ruff check .`,
  `uv run pytest` all clean; landing/demo/data/search/graph/experts/compare browser-verified on the
  live stand.


## Backend Hardening (wave 11, 2026-07-04, branch `feat/backend-hardening` `404a5c3`..`dd23e7e`)

Response to an owner-agent backend review; all 11 items closed, gates green
(`make ci` exit 0, `make eval` status=ok 17/17, pytest 189 passed). Plan:
`.serena/plans/11_BACKEND_HARDENING_PLAN.md`.

- **QA service de-demo'd** (`404a5c3`, `52230ca`): `qa_service.DemoQAService` -> `EvidenceQAService`;
  dead `_fallback_packet`/`_demo_evidence` removed (the `ledger_repository is None` branch returns
  an empty `EvidenceLedgerPacket`); `EvidenceLedgerPort.load_demo_packet` -> `load_evidence_packet`.
  Scoring de-hardcoded from Ni-Cu literals to corpus/element-generic signals
  (`_shared_material_element_count`, generic `_requested_property`/`_regime_matches`,
  `_shared_numeric_bonus`, `_corpus_follow_ups`); the 17 gold questions still pass.
- **Persisted numeric-fact layer** (`c458d9e`): migration `003_numeric_facts.sql` (table
  `numeric_facts` + indexes on source/span/subject/prop). Facts are extracted from every headered
  table row at ingest (`repositories._insert_numeric_facts`) and SQL-queried by QA constraint
  filtering (`list_numeric_facts_for_spans`, `qa_service._numeric_facts_by_span`), falling back to
  `parse_labeled_span_facts` for pre-migration corpora. Arbitrary CSVs without the fixed experiment
  schema now ingest as generic header-labeled table-row spans (`_read_csv_table`/
  `_csv_is_experiment_schema`/`_insert_generic_csv_table`) instead of raising.
- **Sheet provenance + unified decode** (`ab7d2b4`): `ParsedTable.sheet_name` propagated by the
  spreadsheet parser; spreadsheet rows get locator `sheet:<name>:table_NNN:row_NNN` + `{sheet,row,
  headers}` in `locator_json` (`EvidenceSpanFactory.create(locator_extra=...)`); PDF/DOCX keep
  `table_i:row_j`. The two remaining decode bypasses (ingestion head-scan, markdown evidence) now
  use `decode_text_bytes`.
- **SQL graph neighborhood** (`623176a`): `GraphService.neighborhood()` uses
  `DuckDBLedgerRepository.graph_neighborhood()` (depth-limited indexed per-hop SQL) instead of full
  NetworkX materialization; ranking (type_boost + evidence_count) and response shape are
  byte-identical. Migration `004_graph_indexes.sql` indexes `relations(src_entity_id)` /
  `relations(dst_entity_id)`. `build_graph()` kept as a dev/analysis utility, off the request path.
- **Request-scoped label narrowing + semantic verifier** (`dd23e7e`): `AskRequest.allowed_labels`
  (narrow-only, intersected with the deployment `SourceLabelPolicy` via `_effective_label_policy`);
  `ClaimVerifier` gained a rule-based `sentence_semantically_supported` check (content-word
  containment >=0.6 + negation-parity) -> `AnswerVerification.semantic_unsupported_count`, and its
  numeric check now validates fact-backed sentences against ledger fact numbers instead of skipping.
- **Migrations are now `001`..`004`** (glob-runner, each idempotent, re-executed every process start).


## Part 2 — UI integration of the hardening wave (2026-07-04, PR #2 `f9bfb09`)

Merged to `main` and deployed (deploy.yml success; verified live on the stand).
- **Gap relevance-gating** (`qa_service._gaps_for_question` + new `_gap_is_relevant`): gaps are
  filtered by prefix-overlap relevance to the question, so an off-topic question no longer surfaces
  an unrelated packet gap (an earlier live check saw a slag question pull the synthetic Ni-Cu
  conductivity gap). Gold `q_gap_nicu_conductivity` still surfaces its gap (eval verified).
- **Frontend integration** (`apps/web`): `EvaluationDashboard` shows `numeric_mismatch_count` +
  the new `semantic_unsupported_count` (`AskResponse.verification` type extended);
  `uploadArchive()` client + the Data-page upload routes `.zip/.rar/.zip.NNN` to
  `POST /sources/upload-archive` (reports ingested-member count); `AnalysisWorkbench` has an
  «Внешний режим (жюри)» toggle that sends `allowed_labels=[public,internal]` (narrow-only) on the ask.
- Already-integrated before Part 2 (no change): sheet-provenance display (`EvidenceList` renders
  `locator.sheet`), real-case eval (`scripts/run_realcase_eval.py`).
- Gates: `make ci` green (pytest 190 passed + frontend build), `make eval` status=ok 17/17.


## Review-hardening wave (2026-07-04, PR #4 merged + deployed)

Second owner-review (22 items): 14 fixed, 2 already-done (#2 CI push+PR, #21 single-writer by design), 6 deferred.
- **LLM config**: env renamed `DATAEYES_API_BASE/KEY` -> `LLM_API_BASE/LLM_API_KEY`
  (`settings.py` fields `llm_api_base`/`llm_api_key` with `AliasChoices` so legacy
  DATAEYES_* still resolve); default is the Yandex base
  `https://ai.api.cloud.yandex.net/v1`; provider **Yandex AI Studio, model deepseek-4-flash**.
- **Deploy reproducibility**: `docker-compose.server.yml` is now TRACKED in the repo
  (was shipped out-of-band; `git archive HEAD` only ships tracked files). Pins
  `qdrant/qdrant:v1.16.3`; `docker-compose.yml` pinned to match (was `:latest`).
- Archive endpoint rejects multipart parts (`.zip.NNN`/`.partN.rar`) with 400; archive
  members keep their archive-relative path in the ledger (`ingest_upload(filename=member_path)`).
- Generic/experiment CSV first data row is physical row 2 (`start=2`).
- `numeric_facts` surfaced in corpus stats (+by_unit/by_subject); XLSX year/geography derived
  from table content; unit registry extended (economics/energy/depth); `idx_relations_type` added.
- `JURY_ALLOWED_LABELS` server-side visibility floor (runtime); `CORS_ORIGINS` env allowlist.
- Real-case eval (`run_realcase_eval.py`) also asserts semantic_unsupported + evidence-present.

Deferred (P1/P2, tracked): #8 table header detection (blank/title-row skip), #14 batch
skip-manifest persistence, #15 durable reindex jobs table, #17 optional LLM-as-judge strict
semantic mode, #18 numeric_facts as answer rows, #22 experts/laboratories/topics dictionaries.

Ingest blocker found: batch `_embed_many` (yandex.py) bursts `max_workers` concurrent embed
calls -> exceeds the 10-RPS Yandex quota -> 429 -> 7-retry fail; full 4.9GB ingest ~66h. Needs
serialized/paced batch embedding + the quota raised before a full corpus ingest.


## Yandex DENIED -> dataeyes+local pivot (2026-07-04)

CRITICAL: the organizer Yandex key returns 403 PermissionDenied for BOTH the LLM
(gpt://<folder>/deepseek-v4-flash/latest) AND embeddings (foundationModels textEmbedding)
— verified by direct API calls, every auth style. Live demo LLM answers were silently
empty; retrieval degraded to BM25.

Working stack now on the stand (.env):
- LLM = dataeyes (platform.dataeyes.ai/v1, key in .env via DATAEYES_API_BASE/KEY alias):
  LLM_EXTRACTION_MODEL=openai/gpt-5.4-mini, LLM_ANSWER_MODEL=openai/gpt-5.5, LLM_TIMEOUT_S=120.
- Embeddings = LOCAL deepvk/USER-bge-m3 1024-dim (EMBEDDING_BACKEND=local,
  QDRANT_COLLECTION=evidence_local). Yandex embeddings dead.
- Gateway: dual-provider round-robin + failover on ANY provider error (not just 429);
  yandex embed fast-fails on 4xx.
- Verified working: QA returns real cited dataeyes gpt-5.5 answers + local dense retrieval.

Full DATA_HACK ingest reality (8-vCPU stand): 2015 ingestible files (1163 pdf/115 docx/
46 xls/5 pptx + 662 archive members). Docling PDF parse serialized by a thread-lock
(~20-30s/PDF) + local bge-m3 ~300ms/embedding (model NOT cached — redownloads each restart)
=> ~6-10h, CPU-bound. Batch writes to separate DUCKDB_PATH=catalog_full.duckdb +
QDRANT_COLLECTION=evidence_full (zero-downtime) then atomic swap. Speed levers not yet applied:
OpenAI/dataeyes embedding backend (offload CPU) or removing the Docling lock (if thread-safe).
Backups: .env.bak-dataeyes (working), .env.bak-yandex-* (denied Yandex snapshot).


## RESOLVED (2026-07-04): OpenAI embedding backend -> demo works, full batch running

Local bge-m3 too slow on 8-vCPU (0.7 spans/s; fastembed e5-large 4 spans/s). Fix shipped
(PR #7): EMBEDDING_BACKEND=openai -> dense via dataeyes /embeddings (text-embedding-3-small
1536-dim, batched 32/req; 403 above ~32), sparse BM25 local. ~14 spans/s (20x local), embedding
offloaded from CPU. Stand: QDRANT_COLLECTION=evidence_oai, reindex of 12294 spans done.
Demo VERIFIED working: dataeyes gpt-5.5 answers, rich cited output, coverage 1.0, ~20s.
Full DATA_HACK batch running into catalog_full.duckdb + evidence_full_oai (zero downtime),
0 failures, load ~8 healthy; Docling-serialized so ~overnight. Swap procedure:
docs/deployment/full-ingest-runbook.md. Next speed lever: remove Docling _CONVERT_LOCK if thread-safe.


## GPT-5.5 Pro audit fixes (2026-07-04, PR #8 merged + deployed)

10 CONFIRMED findings fixed (verified against code by 4 triage agents first):
- **#1/#8 (P0)**: litellm exceptions are NOT LLMError subclasses -> gateway's bare re-raise on
  exhaustion escaped every `except LLMError` -> /qa/ask could 500 + one span's provider error
  aborted a whole source's extraction. Gateway now wraps terminal failure in LLMError (keeps
  cause); composer + extraction broad-catch -> deterministic/rule-only fallback.
- **#2 (P1)**: zip decompression-bomb caps (per-member + cumulative uncompressed + ratio BEFORE
  write, byte-limited copy, RAR post-extract cap); archive route checks stat().st_size before read_bytes (OOM).
- **#3 (P1)**: SSRF - URL import uses a controlled httpx client (no auto-redirect, revalidate every
  hop vs the public-IP guard, byte cap) instead of trafilatura.fetch_url.
- **#4 (P1)**: batch ingest passes corpus/archive-relative path (provenance) + thread-safe
  content-hash dedup (skip re-extracting duplicates + removes last-writer race).
- **#5 (P1)**: coerce_source_label (fail-closed) + JURY_ALLOWED_LABELS documented+set on stand
  (public,internal) as the mandatory floor. Per-source-label-on-ingest API = documented follow-up.
- **#6 (P1)**: Qdrant _ensure_collection raises EmbeddingDimMismatch (loud) on dim mismatch.
- **#7 (P1)**: direction-inversion gate (sentence_contradicts_cited: negation + monotonic-direction
  flip повышает<->снижает) wired into the composer accept gate (was never running a semantic gate).
- **#9 (P2)**: OpenAI embedding backend validates response count + index set.
- **#10 (P2)**: .env.example documents the working dataeyes+openai profile.

Prod graph: fresh batch running (audit-fixed code, --workers 8, LLM_MAX_CONCURRENCY=16, dataeyes
gpt-5.4-mini extraction + openai embeddings) into catalog_full.duckdb + evidence_full_oai with
relative-path provenance + dedup. 2015 files, ~many hours (large docs are extraction-bound),
resumable. Swap when done via docs/deployment/full-ingest-runbook.md.


## Extraction-speed research + floor (2026-07-04, PR #9)

4-agent + web research on "build the whole graph in minutes". VERDICT: at full
quality it is PHYSICALLY IMPOSSIBLE on this stack.
- **Measured**: dataeyes concurrency ceiling ~16 (32+ concurrent -> HTTP 403 burst guard),
  ~6.6s/call. GLiNER OFF on stand. We already cap LLM at MAX_LLM_SPANS_PER_SOURCE=12/doc.
- **Floor math**: 16 slots / 6.6s = ~2.4 calls/s. 2015 docs x 12 calls = ~24k calls
  -> ~2.8h just LLM (saturated). "Minutes for ALL docs" needs <2 LLM calls/doc =>
  only COARSE LOCAL-ONLY extraction (Slovnet/dictionary + co-occurrence, NO typed LLM
  relations). Self-hosting an LLM on CPU (no GPU) is slower, not faster.
- **Real bottlenecks now**: (1) Docling PARSE of big PDFs — serial by _CONVERT_LOCK
  (Docling not thread-safe), 8-18MB journals take minutes each; (2) the 16-concurrent LLM cap.
- **Ranked levers** (research): #1 bigger chunks/batch-prompt (we already cap calls, so this
  is coverage-per-call not fewer calls); #2 local NER gate to drop empty spans; #3 saturate 16
  slots (DONE, PR #9); #4 prompt-cache + smaller output (~1.5-2x); #5 parallel parse via
  ProcessPoolExecutor(6-8)+OMP_NUM_THREADS=1+pypdfium2 (digital PDFs ~0.1s/doc vs Docling
  minutes) — but pypdfium2 loses Docling table structure (numeric_facts).

DEPLOYED (PR #9): parallelize the 12 per-source LLM calls (were serial -> only ~half the 16
slots used with N workers). ~2x on the LLM-bound path. Parse (big PDFs) is now the co-bottleneck.

Realistic targets: full-quality full corpus ~2-4h; 40 curated small files ~minutes;
coarse-local-only (LLM off) = minutes for all but drops typed relations.

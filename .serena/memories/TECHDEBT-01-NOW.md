<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: f72c7f6 config: answers on deepseek-v4-flash per owner requirement
Scope: src/nornikel_kg/; apps/web/; services/api/; scripts/ingest_corpus.py; pyproject.toml;
  docker-compose.yml; .env.example; .github/workflows/ci.yml; .github/workflows/deploy.yml;
  tests/; .serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md;
  .serena/plans/09_ACCURACY_SOTA_OVERHAUL.md
Area: TECHDEBT
-->

# TECHDEBT-01-NOW

## Purpose

Capture verified current gaps after the accuracy/SOTA overhaul (waves A-D) and the archive/
legacy-format ingestion wave (E), without using memory as a backlog.

## Source Of Truth

- `.github/workflows/ci.yml`: backend job still does not pass `--extra ingest`.
- `.env.example`: `LLM_EXTRACTION_MODEL`/`LLM_ANSWER_MODEL` still blank.
- `eval/gold_questions.yml`, `eval/adversarial_questions.yml`, `eval/expected_spans.yml`:
  orphaned fixtures (see `mem:TEST-01-EVALUATION-GATES`).
- `.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md`: geomechanics gap (G1) still open.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`: waves A-D/E scope and research verdicts.

## Resolved Since The Last Sync (verified, do not re-list as gaps)

All of the following were open gaps recorded in this memory as of `41ee7ac` and are now closed,
verified against the working tree at `3e74473`:

- **Extraction JSON schema was not strict-valid (resolved, `41b3acd`)**: `EXTRACTION_JSON_SCHEMA`
  (`domain/extraction.py`) no longer requests a `confidence` field from the model and its object
  schemas' `required` lists match their `properties` exactly; `adapters/llm/gateway.py:_strictify`
  now also enforces `required = list(properties.keys())` generically for every object node, not
  just `additionalProperties`. This was the root cause of consistently schema-invalid extraction
  payloads recorded as a gap in the prior sync.
- **LLM extraction had no repair/retry path (resolved, `41b3acd`)**: `LiteLLMGateway.generate_json`
  falls back to `json_repair.repair_json` on a JSON decode failure; `ExtractionService._llm_extract`
  retries once with a `ValidationError`-feedback prompt before recording `status="rejected"`.
- **`publication`/`DESCRIBED_IN` outside the declared extraction vocabulary (resolved,
  `41b3acd`)**: both are now in `domain/extraction.py`'s `ENTITY_TYPES`/`RELATION_TYPES` tuples.
- **Dictionary alias scan used raw substring matching (resolved, `41b3acd`)**: `ExtractionService.
  _compiled_alias_patterns` now uses word-boundary regexes with a bounded stem tail for
  pure-Cyrillic aliases and exact matching for digit/Latin-bearing aliases.
- **Author extraction false-hit on abbreviations/bibliography (resolved, `41b3acd`)**:
  `_extract_authors` now requires an affiliation signal near the match and blacklists common EN
  initial pairs ("P.O.", "U.S.", etc.); head-span selection is now document-order (via a stable
  locator sort key), not hash-ordered.
- **Numeric constraints had no unit canonicalization (resolved, `41b3acd`)**: `domain/quantities.py`
  canonicalizes physically-equivalent unit spellings and is precision-first (unit-less
  constraints never filter).
- **canonical_key did not strip edge punctuation or fold homoglyphs (resolved, `41b3acd`)**:
  `domain/normalization.py:canonical_key` now does both, with pure-Cyrillic tokens (alloy codes)
  correctly exempted from homoglyph folding after a caught regression.
- **GLiNER hard-cut chunking sliced entities at chunk boundaries (resolved, `41b3acd`)**:
  `adapters/gliner_ner/extractor.py:sentence_chunks` now splits on sentence boundaries with
  overlap and dedupes by global offset.
- **BM25 sparse search was broken for Russian (resolved, `944e6f0`)**:
  `adapters/embeddings/local.py` now defaults `SPARSE_LANGUAGE=russian`; query vectors use
  `embed_sparse_query` (flat weights) distinct from document `embed_sparse`.
- **No reranking stage over hybrid retrieval (resolved, `944e6f0`)**: `adapters/reranker/
  cross_encoder.py` (`BAAI/bge-reranker-v2-m3`), env-gated via `RERANKER_ENABLED`
  (default `false` until stand latency is measured).
- **Retrieved evidence text lacked document context (resolved, `944e6f0`)**: indexed text is now
  prefixed with the source title.
- **Entity-resolution embedding fallback not wired (resolved, `944e6f0`)**:
  `EntityResolutionService._semantic_match` now calls a `SemanticMatcherPort`
  (`QdrantSemanticMatcher`) with `AUTO_MERGE_THRESHOLD=0.90`/`REVIEW_THRESHOLD=0.80` and a
  digit/short-key veto; wired via `ENTITY_SEMANTIC_FALLBACK=true` (default).
- **Source-scope filters did not propagate into retrieval prefetch (resolved, `944e6f0`)**:
  `adapters/qdrant_index/index.py:hybrid_search` now applies `query_filter` to every `Prefetch`,
  not just the fused query.
- **`_select_experiments` fell back to an arbitrary `experiments[:5]` (resolved, `93f3f87`)**:
  an honest empty list is now returned when no material/property/regime/filter signal matches.
- **Confidence was a blanket "high if non-empty" (resolved, `93f3f87`)**: `_confidence_level` is
  now `"high"` only when the question's material/property signal actually matched.
- **Chemical formulas misread as unknown-material requests (resolved, `93f3f87`)**:
  `_CHEMICAL_FORMULA_VETO` excludes tokens like `co2`/`al2o3`-derived forms.
- **Regime bucketing used the raw regime id, producing fake contradictions (resolved,
  `93f3f87`)**: `domain/analysis.py:_regime_bucket` strips the `reg_`/`regime_` prefix first.
- **Numeric-disagreement conflicts ignored unit/method (resolved, `93f3f87`)**: now requires
  matching canonical unit and equal, non-empty measurement methods.
- **Answer claims were not checked for fabricated numbers (resolved, `93f3f87`)**:
  `domain/answer_claims.py:sentence_numbers_supported` + `ClaimVerifier.numeric_mismatch_count`;
  `LLMAnswerComposer.compose` drops sentences whose numbers aren't in the cited evidence text.
- **Conflicts were attached unconditionally (resolved, `93f3f87`)**: `_conflicts_for_question`
  now gates on shared material/experiment/span with the selected evidence.
- **Cascade delete left orphaned graph references (resolved, `93f3f87`)**:
  `DuckDBLedgerRepository._delete_source_records` now strips deleted span IDs from
  `relations`/`entities` evidence, deleting rows/entities that empty out (dictionary entities
  excepted); `DELETE /sources/{id}` also best-effort deletes the source's Qdrant units.
- **"Experts by topic" neighborhood ranking was not person/publication-aware (resolved,
  `93f3f87`)**: `GraphService.neighborhood` now applies a type boost for `person`/`publication`/
  `team`/`laboratory`.
- **No literature-review grouping in answer synthesis (resolved, `93f3f87`)**:
  `DemoQAService._source_context` + `LLMAnswerComposer._packet_prompt` now carry per-span year/
  geography labels and an explicit grouping instruction.
- **Timeline events without dates (resolved, `41b3acd`+`93f3f87`)**: `ExtractionService.
  _link_publication` now extracts `(year, iso_date)` via `domain/dates.py` and writes them into
  the publication entity's metadata; `GET /graph/timeline` includes dated publications.
- **Per-source retrieval indexing re-embedded the whole entities collection (resolved,
  `b7b12d6`)**: `RetrievalService.index_source(..., include_entities=False)` default off;
  `reindex_all()` indexes entities once at the end.
- **No batch-scale document formats: archives, spreadsheets, legacy .doc (resolved, wave E,
  `2e5458a`)**: `services/archive_expansion.py` (zip/multipart-zip/rar), `adapters/spreadsheet/
  parser.py` (xlsx/xls), `adapters/legacy_doc/parser.py` (doc via antiword/catdoc), `.docm`
  routed through the Docling `.docx` path. `scripts/ingest_corpus.py` and the upload route/UI
  both accept the new formats.
- **Batch ingester could corrupt/hang against a running API's DuckDB lock (resolved,
  `1db832d`)**: `scripts/ingest_corpus.py` now calls `get_ledger_repository().migrate()` up
  front and exits with a clear `SystemExit` message if the ledger cannot be opened; the lock
  contract is documented in the script's own docstring and in
  `docs/deployment/nornikel-nddev.md`.

## Resolved Since The Prior Sync (`3e74473` -> `327f47c`, verified, do not re-list as gaps)

- **litellm's lazy `tenacity` import could kill enrichment threads (resolved, `5194f6c`)**:
  `tenacity>=8.2.0` is now a hard main dependency in `pyproject.toml`.
- **An unhandled error in the enrichment thread stranded a run in "running" forever (resolved,
  `5194f6c`)**: `IngestionService._schedule_enrichment`'s `enrich()` closure now wraps its whole
  body in `try/except`, recording `status="failed"`.
- **A single large Qdrant upsert could exceed the request-size limit (resolved, `67d3bca`)**:
  `QdrantVectorIndex._UPSERT_BATCH = 128` batches all upserts.
- **`nornikel_kg` INFO logs were invisible in the running container (resolved, `67d3bca`)**:
  `services/api/main.py` now sets the logger level and calls `logging.basicConfig` when needed.
- **Per-source retrieval indexing re-embedded every unit even when unchanged (resolved,
  `327f47c`)**: `QdrantVectorIndex.index_units(..., skip_unchanged=True)` hash-skips unchanged
  units via a `text_hash` payload; stale points from a re-parse are pruned afterwards via
  `prune_source_units`.
- **`DemoQAService.ask` re-scanned the full evidence packet on every question (resolved,
  `327f47c`)**: `_load_packet` now caches the packet keyed by `DuckDBLedgerRepository.data_version`.
- **No dashboard-level corpus/audit-trail endpoints for the UI (resolved, PR #18)**:
  `GET /stats/overview` / `GET /stats/answer-runs` (`services/api/routes/stats.py`) plus a
  six-section SPA (`apps/web/src/pages/`).
- **No dense-embedding path that offloads the 8-vCPU stand (resolved, PR #17)**:
  `EMBEDDING_BACKEND=yandex` (`adapters/embeddings/yandex.py`) calls the organizer-provided
  Yandex AI Studio API for dense vectors; sparse BM25 stays local.

## Resolved Since The Prior Sync (`327f47c` -> `652317e`, verified, do not re-list as gaps)

- **The LLM gateway had no client-side pacing or 429 retry (resolved, `6feff7a`)**: new
  `src/nornikel_kg/adapters/ratelimit.py` (`RateLimiter`/`get_limiter`) is a process-wide, named
  min-interval limiter shared by every caller of one provider quota;
  `adapters/embeddings/yandex.py`'s embedding limiter now comes from this shared module
  (`get_limiter("yandex-embeddings", ...)`, code default `YANDEX_EMBED_RPS=8`);
  `adapters/llm/gateway.py:LiteLLMGateway.generate_json` joins a `"llm-completions"` limiter
  (`LLMSettings.llm_rps`, code default `5.0`) and retries `litellm.RateLimitError` up to
  `_RATE_LIMIT_RETRIES = 6` times with jittered exponential backoff inside the existing
  concurrency semaphore (`tests/unit/test_llm_gateway.py::test_gateway_retries_rate_limit`,
  `tests/unit/test_ratelimit.py`). `.env.example`'s stand values raise `LLM_RPS` to `10` and
  `LLM_MAX_CONCURRENCY` to `8` (documented Yandex quota: 10 concurrent generations); code
  defaults (`LLMSettings.llm_rps=5.0`, `llm_max_concurrency=3`) are unchanged.
- **A citation-verified answer without a structured match looked untrustworthy (resolved,
  `ef812af`)**: `services/qa_service.py:DemoQAService._confidence_level` gained
  `summary`/`selected_evidence` parameters; when no experiment matched but the answer is
  citation-verified evidence-grounded (`summary and selected_evidence`), confidence is now
  `"medium"` instead of `"low"`.
- **Answer synthesis pointed readers to table/figure numbers instead of stating values
  (resolved, `24282f1`)**: `services/answer_composer.py`'s `_ANSWER_SYSTEM_PROMPT` now
  explicitly instructs the model to synthesize concrete values/factors and never refer the
  reader to table/figure numbers.
- **No CI/CD auto-deploy path (resolved, `9338017`, merged `652317e` as PR #19)**: new
  `.github/workflows/deploy.yml` ships the tracked tree over SSH on every push to `main`,
  rebuilds `api`/`web`, restarts the stack, and smoke-checks `/api/health` +
  `/api/stats/overview`.

## Resolved Since The Prior Sync (repo-migration squash -> `4ede8c5`, verified, do not re-list as gaps)

- **Questions phrased with a natural-language time scope («за последние 5 лет») were not
  converted into a year filter, and year/geography scope only ever gated the experiment
  table, never the evidence packet handed to answer synthesis (resolved, `4ede8c5`)**:
  `src/nornikel_kg/domain/dates.py:parse_time_scope(question, *, now_year)` recognizes «за
  последние N лет»/`last N years`, «за последний год», RU «с»/«до»/«по» + year (year marker
  required), and `YYYY-YYYY` ranges; a bare year mention with no such phrasing stays a fact,
  not a scope. `services/qa_service.py:DemoQAService._effective_filters` applies the derived
  scope only when the request's explicit `AskFilters.year_from`/`year_to` are unset.
  `_scope_predicate`/`_apply_scope_to_evidence` (new) mean the evidence packet itself is now
  filtered by year/geography, not only `selected_experiments`. A scope derived from question
  text is permissive (keeps sources with no recorded year); an explicit UI/API filter stays
  strict. Verified: `tests/unit/test_dates.py` (2 test functions),
  `tests/unit/test_answer_honesty.py::test_question_time_scope_keeps_unknown_year_sources`,
  and `scripts/run_eval.py`'s `q_year_phrase_is_not_a_filter` (live-run verified in this sync
  pass, `experiment_count: 1`). `uv run pytest` now passes 154 tests (up from 151), 5 skipped
  unchanged; `ruff`/`mypy` both clean (all live-run verified in this sync pass).

## Operational Observations (not test-verified in this repository; dated)

- **Live model bench on a real evidence packet, 2026-07-04, round 1** (cited in the `24282f1`
  commit message, not reproducible from a tracked test/fixture in this sync): answers stayed on
  `aliceai-llm` — 6-11s latency, perfect citation discipline; `qwen3-235b` ran 31s;
  `gpt-oss-120b` ran 26-91s live (unstable) but synthesized factors best; `deepseek-v4-flash`'s
  **raw catalog call** (no `json_repair` in the path) produced broken JSON at 40s; `qwen3.6`
  returned empty content. Dense embedder `text-embeddings/latest` (1536-dim) was confirmed by a
  margin test: +0.30 vs +0.20 (v2) vs +0.16 (v1).
- **Re-bench through the real gateway, same day, round 2 (`f72c7f6`, verified in `.claude/
  CLAUDE.md`/`.env.example` at `HEAD`)**: `deepseek-v4-flash` was re-tested through the actual
  `LiteLLMGateway` path (which includes the `json_repair.repair_json` fallback on a JSON decode
  failure, `mem:ARCH-01-EVIDENCE-MVP`) rather than a raw catalog call — 4/4 verified synthesis,
  citation coverage 1.0, zero numeric fabrication, richer author/factor detail than
  `aliceai-llm`, ~17s warm. The stand now answers on `deepseek-v4-flash` (owner requirement);
  `.env.example`'s `LLM_TIMEOUT_S` was raised `30`->`60` to fit the higher latency. Extraction
  stays on `aliceai-llm` (native strict-JSON, ~7x faster on the batch path, graph already
  built). Catalog constraint (reported, not independently re-verified in this sync): only
  `deepseek-v4-flash` exists in the organizer's Yandex AI Studio catalog — `deepseek-v4`,
  `deepseek-v4-pro`/`-r1`/`-v3.2` all return HTTP 400. The concrete `LLM_ANSWER_MODEL`/
  `LLM_EXTRACTION_MODEL` strings live only in the server's untracked `.env` (`LLM_ANSWER_MODEL`/
  `LLM_EXTRACTION_MODEL` stay blank in the tracked `.env.example`); the switch is persistent on
  the server and re-read on every `docker compose ... up -d` (including the auto-deploy
  workflow's redeploy step), but this specific mechanism is not independently verifiable from
  this repository. Treat both benches as dated operational notes, not regression-tested
  guarantees — no tracked benchmark artifact backs these numbers.

## Entry Points

- `EntityResolutionService.resolve_or_create`: exact key -> alias -> semantic -> create.
- `GET /graph/timeline` (`services/api/routes/graph.py`).
- `ExtractionService.mention_extractor` (GLiNER lazy import).
- `ExtractionService._llm_mentions`: LLM extraction call site, gated by `LLM_EXTRACTION_ENABLED`.
- `GET /stats/overview` / `GET /stats/answer-runs` (`services/api/routes/stats.py`).
- `YandexEmbeddingBackend._embed_one` (`adapters/embeddings/yandex.py`): Yandex AI Studio
  embedding call site, gated by `EMBEDDING_BACKEND=yandex`.

## Current Behavior

The system is a working evidence-led product with real ingestion (Docling/trafilatura/pandas/
antiword-catdoc, plus zip/rar archive expansion), extraction (dictionary+GLiNER+optional-LLM
with typed relations), retrieval (Qdrant hybrid with Russian BM25 and an optional cross-encoder
rerank), LLM-gated answer synthesis with a numeric-fabrication gate, graph analytics
(type-aware neighborhood ranking, cascade-safe deletion, dated publication timeline), scoped QA
filters (unit-canonicalized numeric constraints, geography, year), and honest confidence/gap/
conflict signaling with no arbitrary fallback rows, incremental hash-skip Qdrant indexing, and a
data-version-cached evidence packet, quota-paced/retrying LLM and embedding gateways, and
auto-deploy on push to `main`. `uv run pytest` passes 154 tests, 5 skipped, at `4ede8c5`
(live-run verified in this sync pass); `ruff`/`mypy` both clean (live-run verified, mypy: "no
issues found in 76 source files").

## Contracts And Data

The current demo answer must remain evidence-first regardless of which extraction/retrieval
paths are enabled: answer summary sentences cite spans and pass the numeric-fabrication check,
evidence cards expose `EvidenceSpan` IDs, and graph paths connect material, experiment, regime,
step, measurement, property, evidence, and document.

## Invariants

- Keep the deterministic synthetic demo green while any LLM/retrieval path is toggled on or off.
- Do not let Qdrant become the authoritative evidence or entity store.
- Do not introduce LLM-generated claims without supporting span IDs, and never let an answer
  sentence's cited numbers diverge from the literal cited evidence text (fact-backed sentences
  with `supporting_fact_ids` are the only exception).
- Only `src/nornikel_kg/adapters/llm/gateway.py` may import `litellm`.
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()`; batch scripts
  must stop the `api` container first (`scripts/ingest_corpus.py` now fails fast otherwise).

## Change Rules

When closing a gap below, verify it against the working tree (not this memory) before removing
it, and move the corresponding "Resolved Since" bullet into the resolved list above in the same
change.

## Known Gaps

- **`изи-никель.рф` primary domain may not resolve yet (unverified operational note, dated
  2026-07-04)**: `.claude/CLAUDE.md`/`docs/deployment/nornikel-nddev.md` document the DNS
  prerequisite (an A record for `изи-никель.рф`/`www` -> `165.22.203.232`; the host's
  acme-companion issues the TLS certificate automatically once the name resolves), but neither
  tracked file states whether that A record has already been created. Per the launching
  coordinator's report (not verifiable from any tracked artifact — no DNS-status file exists in
  this repository), the record had not yet been created by the domain owner as of this sync.
  `https://nornikel.nddev.asia` remains the working mirror in the meantime.
- **Geomechanics domain not covered by the ontology**: the dictionary extension (`58760b3`,
  unchanged this sync) added pyrometallurgy/electrowinning/flotation/desalination terms but no
  geomechanics-specific materials/regimes (verified: no matching alias hits in any dictionary
  file), so questions specific to that domain in the real corpus still slot-parse to no entities.
- **Eval questions target only the synthetic fixture**: `scripts/run_eval.py`'s hardcoded
  `EVAL_QUESTIONS` (17 questions, up from 12 — 5 new cases add conflict-surfacing, numeric
  constraint, year-phrase-is-not-a-filter, and two prompt-injection adversarial cases) still run
  against the synthetic `sample_docs/synthetic`/`synthetic_v2` corpora only; there is still no
  gold-question set for the real `DATA_HACK/` corpus, so `make eval` does not exercise the
  ontology/publication/scope-filter/reranker behavior against real data — only
  `tests/unit/test_scope_and_constraints.py` and the new `tests/unit/test_*_accuracy.py` /
  `test_answer_honesty.py` modules do, against synthetic/in-memory fixtures.
- **GLiNER model not pre-pulled in CI**: `.github/workflows/ci.yml`'s backend job does not
  install the `ingest` optional dependency group; `GLINER_ENABLED` defaults to `true` at
  runtime, but CI's `pytest` run never exercises the real GLiNER/reranker/spreadsheet-parser
  paths (those tests use `pytest.importorskip`).
- `eval/gold_questions.yml`, `eval/adversarial_questions.yml`, `eval/expected_spans.yml` are
  orphaned: no code path reads them; `scripts/run_eval.py` hardcodes its own 17-question list
  instead (see `mem:TEST-01-EVALUATION-GATES`).
- **Real-corpus `.docm` files quarantined in practice (reported, not test-verified)**: per the
  launching agent's report of the live stand's re-enrichment run, at least one real `.docm` file
  from the corpus was quarantined by the Docling backend despite the `.docm`-as-`.docx` stream
  rename in `adapters/docling/parser.py`. This repository sync could not independently verify
  the claim against a live Docling run or a stand log (no such artifact exists in the working
  tree); `tests/unit/test_corpus_formats.py::test_docm_routes_through_document_parser` only
  proves the routing (a stub parser is called with the right filename/extension), not that a
  real Docling conversion of a `.docm` file with macros/complex layout always succeeds. Treat
  this as an open, unverified operational observation, not a proven code defect.
- **Reranker latency measured and kept off**: `RERANKER_ENABLED` defaults to `false` in code
  (`src/nornikel_kg/services/runtime.py`); `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`'s "Deploy
  results" section records a live measurement of `bge-reranker-v2-m3` at 58s warm per question
  (30 pairs, 8 shared vCPU) versus 8.4s without reranking, and keeps it off pending int8
  quantization or a smaller reranker model. `ENTITY_SEMANTIC_FALLBACK` defaults to `true`; its
  live-stand latency is not separately recorded in tracked artifacts.
- **Yandex embedding quota is shared and fixed at 10 RPS**: `adapters/ratelimit.py`'s
  `RateLimiter` (obtained via `get_limiter("yandex-embeddings", ...)` in
  `adapters/embeddings/yandex.py`) paces requests via `YANDEX_EMBED_RPS` (code default `8`,
  `.env.example` stand value `9.5`) to stay under the folder's 10 RPS quota. `.env.example`'s
  comment records that Yandex Cloud's self-service Quota Manager does not cover AI Studio —
  raising the quota requires a support ticket from the cloud owner (organizers), not
  configurable in this repository. The LLM completions path shares the same limiter module
  (`"llm-completions"` named limiter, `LLM_RPS` code default `5.0`, stand value `10`) and now
  retries `litellm.RateLimitError` with backoff instead of failing outright (`6feff7a`,
  see "Resolved Since" above).
- **No real-corpus gold evaluation set**: `scripts/run_eval.py`'s `EVAL_QUESTIONS` (17 questions,
  unchanged this sync) still targets only the synthetic corpora; see the eval-questions gap
  above for detail.
- **CI still runs without the `ingest` extra**: `.github/workflows/ci.yml`'s backend job does not
  install GLiNER/Docling/spreadsheet/legacy-doc dependencies (unchanged this sync, see the GLiNER
  gap above).

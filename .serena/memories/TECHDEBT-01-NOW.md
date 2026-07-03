<!-- Memory Metadata
Last updated: 2026-07-03
Last commit: 3e74473 docs(deploy): DuckDB lock contract and archive-aware batch procedure
Scope: src/nornikel_kg/; apps/web/; services/api/; scripts/ingest_corpus.py; pyproject.toml;
  docker-compose.yml; .env.example; .github/workflows/ci.yml; tests/;
  .serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md; .serena/plans/09_ACCURACY_SOTA_OVERHAUL.md
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

## Entry Points

- `EntityResolutionService.resolve_or_create`: exact key -> alias -> semantic -> create.
- `GET /graph/timeline` (`services/api/routes/graph.py`).
- `ExtractionService.mention_extractor` (GLiNER lazy import).
- `ExtractionService._llm_mentions`: LLM extraction call site, gated by `LLM_EXTRACTION_ENABLED`.

## Current Behavior

The system is a working evidence-led product with real ingestion (Docling/trafilatura/pandas/
antiword-catdoc, plus zip/rar archive expansion), extraction (dictionary+GLiNER+optional-LLM
with typed relations), retrieval (Qdrant hybrid with Russian BM25 and an optional cross-encoder
rerank), LLM-gated answer synthesis with a numeric-fabrication gate, graph analytics
(type-aware neighborhood ranking, cascade-safe deletion, dated publication timeline), scoped QA
filters (unit-canonicalized numeric constraints, geography, year), and honest confidence/gap/
conflict signaling with no arbitrary fallback rows. `uv run pytest` passes 141 tests, 4 skipped,
at `3e74473` (live-run verified in this sync pass); `ruff`/`mypy` both clean (live-run verified).

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
- **Reranker/entity-semantic-fallback latency not measured on the stand**: `RERANKER_ENABLED`
  defaults to `false` and `ENTITY_SEMANTIC_FALLBACK` defaults to `true` in code
  (`src/nornikel_kg/services/runtime.py`), but this repository sync only verifies the code
  contract, not a live-stand latency measurement — that is deploy-operational information
  outside this repository's tracked artifacts.

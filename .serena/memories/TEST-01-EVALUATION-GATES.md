<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: ec79a96 docs: изи-никель.рф is primary, nornikel.nddev.asia is the mirror
Scope: Makefile; tests/; scripts/run_eval.py; eval/; .github/workflows/ci.yml; pyproject.toml
Area: TEST
-->

# TEST-01-EVALUATION-GATES

## Purpose

Capture required verification and acceptance gates after the accuracy/SOTA overhaul (waves A-D)
and the archive/legacy-format ingestion wave (E).

## Source Of Truth

- `scripts/run_eval.py`: hardcoded `EVAL_QUESTIONS` list, now **17** question dicts (verified via
  `grep -c '"question_id":'`), run against the live `DemoQAService` and a temp-copy DuckDB
  ledger, covering only the synthetic corpus.
- `eval/gold_questions.yml`, `eval/adversarial_questions.yml`, `eval/expected_spans.yml`: legacy
  YAML fixtures kept in the repo but not referenced by any code path.
- `tests/unit/`: ID stability, claim verifier, source-label policy, dictionary-loader, LLM
  gateway, entity resolution, extraction service, retrieval service, answer composer, ingestion
  service, scope/constraint tests, plus new (this sync) `test_quantities_and_dates.py`,
  `test_extraction_accuracy.py`, `test_retrieval_and_resolution_accuracy.py`,
  `test_answer_honesty.py`, `test_corpus_formats.py`.
- `tests/integration/`: FastAPI, DuckDB ledger, graph API, ingest API, synthetic-v2-corpus, plus
  new `test_analytics_api.py`.
- `make ci` / `make eval`: local gates matching CI.

## Current Behavior

`uv run pytest` passes **151 tests, 5 skipped** at `652317e` — verified by a live run in this
sync pass, an increase of 3 passed over the previously recorded 148-passed/5-skipped baseline at
`327f47c` (skip count unchanged). `uv run ruff check .` and `uv run mypy` both pass clean
(live-run verified in this sync pass; mypy: "no issues found in 76 source files").

The 5 skips remain `pytest.importorskip` guards for optional heavy dependencies (`docling`,
`trafilatura`, `fastembed`, and similar), unchanged this sync.

New test modules/functions this sync (all passing):
- `tests/unit/test_ratelimit.py` (new, 2 test functions): `RateLimiter` spaces requests to the
  configured interval; `get_limiter` returns the same shared instance for a repeated name.
- `tests/unit/test_llm_gateway.py` gained `test_gateway_retries_rate_limit`: a `litellm.
  RateLimitError` on the first two attempts is retried and the third attempt's response is
  returned, proving the gateway does not fail a call on a transient 429.

Test modules added the prior sync (unchanged this sync):
- `tests/unit/test_yandex_embeddings.py` (5 test functions): `YandexEmbeddingBackend` credential
  requirement, doc/query model-URI split, `embed_dense` order preservation, sparse-stays-local
  flat query weights (`pytest.importorskip("fastembed")`-gated), query-embedding cache hits.
- `tests/unit/test_answer_honesty.py` gained one function,
  `test_packet_cache_invalidated_by_data_version`: verifies `DemoQAService._load_packet()` caches
  while `data_version` is unchanged and invalidates after a ledger-mutating write.
- `tests/integration/test_analytics_api.py` gained two functions, `test_stats_overview_counters`
  and `test_answer_runs_audit_trail`: route-level coverage for the new
  `GET /stats/overview`/`GET /stats/answer-runs` endpoints.

Prior-sync test modules (unchanged this sync):
- `tests/unit/test_quantities_and_dates.py` (9 test functions): unit canonicalization equivalence
  (мг/дм³≡мг/л etc.), numeric-constraint parsing (single/range/RU-operator forms), unit-mismatch
  non-filtering, year-marker-guarded year extraction, bare-year rejection (Kelvin/sample codes).
- `tests/unit/test_extraction_accuracy.py` (9 test functions): word-boundary alias matching
  (no false hits inside longer words), author-extraction affiliation gating and EN-initials
  blacklist, canonical-key edge-punctuation stripping and mixed-vs-pure-script homoglyph folding.
- `tests/unit/test_retrieval_and_resolution_accuracy.py` (6 test functions): BM25
  `SPARSE_LANGUAGE` wiring, reranker candidate-pool behavior, semantic entity-resolution
  auto-merge/review thresholds and digit veto.
- `tests/unit/test_answer_honesty.py` (7 test functions): honest empty answers for irrelevant
  questions, chemical-formula veto, conflict relevance gating, numeric-fabrication rejection in
  `ClaimVerifier`/`LLMAnswerComposer`.
- `tests/unit/test_corpus_formats.py` (7 test functions): plain-zip/multipart-zip/zip-slip/
  corrupt-rar archive expansion, spreadsheet-parser table rows, legacy-doc `ParserError` on
  empty extraction, `.docm` routing through the document parser.
- `tests/integration/test_analytics_api.py` (7 test functions): route-level coverage for
  `/gaps/analyze`, `/graph/timeline` (incl. dated publications), `/sources/{id}/enrich`,
  `/sources/reindex-all`.

`scripts/run_eval.py`'s `EVAL_QUESTIONS` grew from 12 to 17 questions this wave: the original 12
(ideal Ni-30Cu scenario, Cyrillic-alias resolution, provenance, comparison, gap, conflict,
unknown-material negative controls, exact spaced-material scoping, one broad family query) plus
5 new cases — `q_conflict_surfaced_for_question` (asserts `min_conflict_count >= 1`),
`q_numeric_constraint_hv` (asserts the constrained material's HV values respect a
`max_measurement_value_hv` ceiling), `q_year_phrase_is_not_a_filter` (asserts «до 2020 года»
does not silently drop a valid Ni-30Cu experiment), `q_injection_ignore_instructions` (asserts
`max_source_label_leaks = 0` under a prompt-injection attempt), and `q_injection_fake_span`
(asserts a `forbidden_answer_substrings` check that a fabricated "999 HV" claim never appears in
the answer). `main()` now also asserts `numeric_mismatch_count == 0` and
`citation_coverage >= 1.0` for every question, in addition to the prior
`unsupported_claim_count`/`source_label_leak_count` gates.

CI runs the same backend (`uv sync --group dev`, `ruff`, `mypy`, `pytest`,
`uv run python scripts/run_eval.py`) and frontend (`npm ci`, `typecheck`, `build`) checks; the
backend job still does not pass `--extra ingest` (`mem:TECHDEBT-01-NOW`).

## Contracts And Data

Non-negotiable demo gates are now `unsupported_claim_count = 0`, `source_label_leak_count = 0`,
`numeric_mismatch_count = 0`, and `citation_coverage >= 1.0`; `run_eval.py` raises
`SystemExit(1)` if any `EVAL_QUESTIONS` case fails its assertions.

`tests/unit/test_scope_and_constraints.py` protects: RU/symbolic numeric-constraint parsing and
filtering (now via `domain/quantities.py`), the real-domain dictionary extension's
resolvability, publication/author graph linking, and geography/year scope filtering — all
against synthetic in-memory DuckDB fixtures built with
`DuckDBLedgerRepository(tmp_path / "scope.duckdb")`.

## Invariants

- Do not mark a demo answer successful if unsupported final sentences exist, or if any cited
  number in the answer diverges from the literal cited evidence text.
- Do not mark a security run successful if restricted evidence enters the context packet or if a
  prompt-injection attempt causes a source-label leak.
- Whenever `scripts/run_eval.py`'s `EVAL_QUESTIONS` changes, keep the question count and this
  memory's description in sync in the same change; do not resurrect `eval/*.yml` as a second
  source of truth without wiring it into code first.
- Whenever the real-corpus ontology, scope filters, or accuracy fixes change, extend the relevant
  `tests/unit/test_*_accuracy.py`/`test_answer_honesty.py`/`test_quantities_and_dates.py` module
  in the same change.

## Change Rules

When new ingestion/retrieval/extraction behavior is added, extend `EVAL_QUESTIONS` in
`scripts/run_eval.py` and the relevant `tests/unit/` or `tests/integration/` module in the same
change.

## Verification

- `make ci`: ruff, mypy, pytest (151 passed, 5 skipped at `652317e`, live-run verified), frontend
  typecheck, build.
- `make eval`: `scripts/run_eval.py` — 17-question live QA metrics against the synthetic DuckDB
  ledger only, incl. adversarial injection assertions.
- `docker compose config`: Compose validation.

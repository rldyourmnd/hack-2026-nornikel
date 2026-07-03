<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 8d10cc4 chore: untrack the 56MB design reference package
Scope: README.md; apps/web/; services/api/; src/nornikel_kg/; eval/; sample_docs/; scripts/; .serena/plans/10_AUDIT_RESPONSE_PLAN.md; src/nornikel_kg/domain/encoding.py;
  src/nornikel_kg/domain/table_facts.py; src/nornikel_kg/domain/geography.py;
  scripts/run_realcase_eval.py
Area: CORE
-->


# CORE-01-INDEX

## Purpose

Index the durable project knowledge for the Nornikel Materials KG Search hackathon MVP.

## Source Of Truth

- `README.md`: repository overview, quick start, demo scenario, and implemented scope.
- `AGENTS.md`: Codex-native project instructions and plugin/tooling policy.
- `.claude/CLAUDE.md`: Claude Code project memory and operational commands.
- `apps/web/`: React/Vite app, now a `react-router-dom` v7 multi-page app
  (`apps/web/src/app/ui/App.tsx`) with routes `/` (`pages/landing`), `/search`, `/graph`, `/data`,
  `/analytics`, `/compare`, `/experts`, `/eval`, `/security`, `/demo` under a shared `AppLayout`
  (`apps/web/src/widgets/app-layout/`: `Header` + `Footer`, replacing the old sidebar-nav SPA
  shell); see `mem:ARCH-01-EVIDENCE-MVP`'s "Frontend Redesign" section for the verified detail.
- `services/api/`: FastAPI route layer, now including `services/api/routes/stats.py`.
- `src/nornikel_kg/`: backend domain, ports, adapters, and application services.
- `scripts/ingest_corpus.py`: batch-ingests a real document corpus directory into the ledger
  inside the API container; fails fast at start if the ledger cannot be opened (mutually
  exclusive with a running `api` container — see `mem:RELEASE-01-VALIDATION`).
- `eval/`: legacy YAML gold/adversarial fixtures; not read by any code path (`mem:TEST-01-EVALUATION-GATES`).
- `sample_docs/synthetic/`: original P0 fixture. `sample_docs/synthetic_v2/`: W5 17-source synthetic corpus with `manifest.json`.
- `tests/`: unit and integration tests (154 passed, 5 skipped at `4ede8c5`, live-run verified).
- `docs/deployment/nornikel-nddev.md`: primary live-stand deployment contract.
- `.serena/plans/08_TRACK_FULL_REQUIREMENTS_AND_GAPS.md`: full-track requirement brief («Научный
  клубок») and gap analysis G1-G10 against the real `DATA_HACK/` corpus.
- `.serena/plans/09_ACCURACY_SOTA_OVERHAUL.md`: the accuracy/SOTA overhaul plan (waves A-D,
  landed as PR #15) plus wave E (archive/legacy-format ingestion, PR #16), plus a "Deploy
  results (measured on the stand, 2026-07-03)" section recording live deploy observations.
- `.serena/reviews/`: tracked plan critical review and research evidence register.

## Repository Identity And History (verified 2026-07-04)

- Working repository: `origin` = `git@github.com:rldyourmnd/hack-2026-nornikel.git`
  (`git remote -v`). `main`/`origin/main` is the canonical branch; the auto-deploy
  workflow (`.github/workflows/deploy.yml`) runs from here on every push to `main`
  (`gh api repos/rldyourmnd/hack-2026-nornikel/actions/workflows` -> `deploy` state
  `"active"`).
- Archive repository: `legacy-origin` = `git@github.com:rldyourmnd/nornikel-kg-search.git`,
  a frozen pre-migration archive (`.claude/CLAUDE.md`'s Scope section, `AGENTS.md`'s Key
  Notes, both added in commit `919a636`: "do not push there"). It carries the same
  `.github/workflows/deploy.yml` file, but the workflow is manually disabled there
  (`gh api repos/rldyourmnd/nornikel-kg-search/actions/workflows` -> `deploy` state
  `"disabled_manually"`, verified 2026-07-04) — pushes to `legacy-origin` never trigger a
  deploy.
- **History-rewrite caveat**: `hack-2026-nornikel`'s `main` is a freshly squashed history
  (`git log --oneline`: `40eb27c` bootstrap .. `919a636` migration doc .. `bb45bce` HEAD —
  24 commits total), built during the 2026-07-03 migration. Commit SHAs cited deep in this
  memory file and in `mem:ARCH-01-EVIDENCE-MVP`/`mem:DATA-01-EVIDENCE-LEDGER`/
  `mem:RELEASE-01-VALIDATION`/`mem:TECHDEBT-01-NOW`/`mem:TEST-01-EVALUATION-GATES`/
  `mem:SEC-01-ACL-AND-PROMPT-INJECTION` (e.g. `652317e`, `ec79a96`, `9338017`, `41b3acd`,
  `944e6f0`, `93f3f87`, `58760b3`) predate this squash and are **not** ancestors of the
  current `HEAD` (verified: `git merge-base --is-ancestor ec79a96 HEAD` fails; `git
  merge-base --is-ancestor ec79a96 legacy-origin/main` succeeds). Those SHAs remain
  resolvable in this local checkout only because `legacy-origin`'s objects are fetched
  here — they identify commits on the archived `nornikel-kg-search` line, not on
  `hack-2026-nornikel`'s `main`. Treat every such pre-`919a636` SHA as archive-repo
  provenance for the described change, not as a commit reachable from this repo's `HEAD`.
  The described code behavior itself has been independently re-verified against the
  working tree at `bb45bce` in this sync pass (see `## Current Behavior` below and the
  per-file Source Of Truth citations, which are path-based and still accurate).

## Entry Points

- `mem:ARCH-01-EVIDENCE-MVP`: architecture, module boundaries, ports/adapters, and stack decisions.
- `mem:DATA-01-EVIDENCE-LEDGER`: evidence IDs, DuckDB ledger, graph/entity schema, and answer claims.
- `mem:SEC-01-ACL-AND-PROMPT-INJECTION`: source-label filtering, prompt-injection, and internal-document safety invariants.
- `mem:TEST-01-EVALUATION-GATES`: required checks, metrics, and acceptance gates.
- `mem:DOCS-01-PLANNING-SOURCE`: planning-doc ownership and current implementation status.
- `mem:RELEASE-01-VALIDATION`: validation, CI, Compose, and deployment checks.
- `mem:TECHDEBT-01-NOW`: verified current gaps and migration triggers.

## Current Behavior

Since the last sync (`65af046`), twelve commits landed the Yandex AI Studio integration plus a
resilience/perf/UI follow-on, all verified against the working tree at `327f47c`:

- **Yandex AI Studio embeddings backend** (`7c5d30b` feat, `210bddd`/`d17675f`/`fa4e637` fixes,
  merged `6d8c7ff` as PR #17): `src/nornikel_kg/adapters/embeddings/yandex.py`
  (`YandexEmbeddingBackend`) — dense 1536-dim embeddings via the canonical
  `https://ai.api.cloud.yandex.net/foundationModels/v1/textEmbedding` host, `x-folder-id`
  header, 4000-char input truncation (documented 2048-token cap), 7 retries with exponential
  backoff + jitter, and a process-wide `_RateLimiter` (`YANDEX_EMBED_RPS`, default 8 — paces
  requests below the shared 10 RPS folder quota, since retry-only backoff alone loses against a
  saturated quota under concurrency). A module-level query-embedding cache
  (`_query_cache`/`_QUERY_CACHE_MAX = 256`) spares repeat demo questions. Sparse BM25 stays local
  (`embed_sparse`/`embed_sparse_query` delegate to `LocalEmbeddingBackend`). Wired into
  `services/runtime.py` via `EMBEDDING_BACKEND=yandex`. `src/nornikel_kg/ports/retrieval.py`'s
  `EmbeddingBackendPort` gained `embed_dense_query` (distinct query-vector method, implemented by
  `local.py`/`fake.py`/`yandex.py`); `QdrantVectorIndex.hybrid_search`/`dense_search` now call
  `embed_dense_query` instead of `embed_dense` for the query side.
- **Resilience fixes** (`5194f6c`): `tenacity>=8.2.0` is now a hard main dependency in
  `pyproject.toml` (litellm's `num_retries` path imports it lazily and raised a bare exception
  when absent — observed live killing enrichment threads); `IngestionService._schedule_enrichment`
  now guards its entire thread body in `try/except` and records `status="failed"` instead of
  silently stranding a run in "running" forever; entity-collection naming made dimension-safe
  (see below).
- **Process-wide embedding rate limiter + reindex marker** (`ee641dd`): the `_RateLimiter`
  described above, plus `RetrievalService.reindex_all()` logging `"Reindex complete: %d units"`
  as an ops-greppable completion marker.
- **PR #18 "sectioned UI"** (`98fc57e` feat, merged `53191d2`): `apps/web/src/pages/` gained
  `graph/`, `data/`, `analytics/`, `eval/`, `security/` alongside `workbench/`;
  `WorkbenchPage.tsx` renders six nav sections (Поиск/Граф знаний/Данные/Аналитика/Качество/
  Безопасность); `AnalysisWorkbench.tsx` was slimmed to the search view and gained an
  `injectedQuestion?: string | null` prop; `ArtifactBankPanel.tsx` gained an optional
  `onEnrich?: (sourceId: string) => Promise<void>` prop. New `services/api/routes/stats.py`
  exposes `GET /stats/overview` (`DuckDBLedgerRepository.corpus_stats()`) and
  `GET /stats/answer-runs` (`list_answer_runs(limit)`), covered by
  `tests/integration/test_analytics_api.py::test_stats_overview_counters`/
  `test_answer_runs_audit_trail`.
- **Qdrant fixes** (`67d3bca`): `QdrantVectorIndex._UPSERT_BATCH = 128` (a single ~1700-point
  x 1536-dim upsert exceeded Qdrant's request-size limit, observed as a live 400); `services/api/main.py`
  now sets `logging.getLogger("nornikel_kg").setLevel(logging.INFO)` and calls
  `logging.basicConfig(level=logging.INFO)` if no root handler exists, so reindex/enrichment INFO
  logs are visible in the container.
- **Perf wave** (`327f47c`): `QdrantVectorIndex.index_units(..., skip_unchanged=True)` is
  incremental — each point carries a `text_hash` payload, unchanged units are hash-skipped before
  ever calling the embedding API, and stale points from a re-parse are pruned afterwards via
  `prune_source_units` (no delete-before-index, so a failed re-embed never loses vectors);
  `RetrievalService.index_source` uses this contract and `reindex_all()` logs the completion
  marker above. `DuckDBLedgerRepository` gained a `_data_version` counter (bumped on
  ingest/delete/`set_source_metadata` writes) and a public `data_version` property;
  `DemoQAService._load_packet` caches the loaded `EvidenceLedgerPacket` keyed by that version
  (a full ~12k-span scan per `ask` previously dominated latency).

- **Quota-aware LLM gateway + shared rate limiter** (`6feff7a`): new `src/nornikel_kg/adapters/ratelimit.py`
  (`RateLimiter`/`get_limiter`) is a process-wide, named min-interval limiter shared by every
  caller of one provider quota. `adapters/embeddings/yandex.py` now gets its limiter from this
  module (`get_limiter("yandex-embeddings", ...)`, code default `YANDEX_EMBED_RPS=8`,
  `.env.example` stand value `9.5`) instead of a private module-level limiter.
  `adapters/llm/gateway.py`'s `LiteLLMGateway.generate_json` joins a `"llm-completions"` limiter
  (`LLMSettings.llm_rps`, code default `5.0`, `.env.example` stand value `10`) and retries
  `litellm.RateLimitError` up to `_RATE_LIMIT_RETRIES = 6` times with jittered exponential
  backoff inside the existing concurrency semaphore; `LLMSettings.llm_max_concurrency` code
  default stays `3`, `.env.example`'s stand value is raised to `8` (documented Yandex quota: 10
  concurrent generations). `.env.example` also records that Yandex Cloud's self-service Quota
  Manager does not cover AI Studio — raising the 10 RPS embeddings quota needs a support ticket
  from the cloud owner (organizers).
- **Honest "medium" confidence for verified answers without a structured match** (`ef812af`):
  `services/qa_service.py:DemoQAService._confidence_level` gained `summary`/`selected_evidence`
  parameters; a citation-verified answer with no structured-experiment match now returns
  `"medium"` (previously `"low"`, indistinguishable from "nothing found").
- **Answer prompt demands synthesis over table references** (`24282f1`):
  `services/answer_composer.py`'s `_ANSWER_SYSTEM_PROMPT` now explicitly instructs the model to
  synthesize concrete values/factors instead of pointing the reader to table/figure numbers
  (live model bench on a real packet, 2026-07-04: `aliceai-llm` was the answer model at that
  point — 6-11s, perfect citation discipline; `gpt-oss-120b` synthesized factors best but ran
  26-91s live, too slow for interactive use). **Superseded same day by `f72c7f6`** ("config:
  answers on deepseek-v4-flash per owner requirement", verified in `.claude/CLAUDE.md` and
  `.env.example` at `HEAD`): the answer model is now `deepseek-v4-flash` (owner requirement,
  re-benched through the real LiteLLM gateway — `json_repair` recovers its non-native JSON,
  4/4 verified synthesis, citation 1.0, zero numeric fabrication, richer author/factor detail,
  ~17s warm, `LLM_TIMEOUT_S` raised `30`->`60`). **Extraction moved to `deepseek-v4-flash` too,
  same day (`42ca7ba`, verified in `.claude/CLAUDE.md`/`.env.example` at `HEAD`)**, owner
  requirement: isolation bench reported 0/6 JSON failures and more relations/span than
  `aliceai-llm` (~16s/span, 2.4x slower per span); the full corpus was re-extracted and the
  graph rebuilt clean — 3107 entities / 6771 relations with a tight R&D ontology, versus the
  prior `aliceai-llm` extraction's 4206/16560 (reported noisy 100+-type tail). Connectivity
  spot-check («Медный штейн»): 154 evidence spans, 111 typed edges. `aliceai-llm` (native
  strict-JSON, 2.4s) remains in the catalog as a fast fallback, not the active path. See
  `mem:TECHDEBT-01-NOW` and `mem:DATA-01-EVIDENCE-LEDGER` for the full bench/graph-rebuild
  history, including the earlier raw-catalog DeepSeek call that produced broken JSON before
  `json_repair` was in the path.
- **GitHub Actions auto-deploy + `изи-никель.рф` primary domain** (`9338017`, merged `652317e`
  as PR #19): new `.github/workflows/deploy.yml` ships the tracked tree over SSH on every push
  to `main`, rebuilds `api`/`web`, restarts the stack and smoke-checks `/api/health` +
  `/api/stats/overview` (secrets `DEPLOY_SSH_KEY`/`DEPLOY_HOST`/`DEPLOY_USER`,
  concurrency-guarded, group `deploy-production`). Primary stand domain is now
  `https://изи-никель.рф` (punycode `xn----jtbedbbojo8m.xn--p1ai`), with
  `https://nornikel.nddev.asia` kept as a secondary mirror (`.claude/CLAUDE.md`/
  `docs/deployment/nornikel-nddev.md`, `ec79a96` corrected "alias" wording to "mirror").
  `.env.example`'s `APP_BASE_URL` now defaults to `https://изи-никель.рф`. Both docs record a DNS
  prerequisite: an A record for `изи-никель.рф`/`www` pointing at `165.22.203.232`, after which
  the host's acme-companion issues the certificate automatically. Per the launching
  coordinator's report (not independently verifiable from any tracked artifact in this
  repository — no DNS-status file exists in the tree): the A records had not yet been created by
  the domain owner as of this sync, so the new primary domain does not yet resolve/serve; treat
  this as an unverified operational note, not a proven fact (see `mem:TECHDEBT-01-NOW`).

Two more commits landed after the `652317e`/`ec79a96` state described in the paragraphs
above (both still verified present in the current squashed history, `git log --oneline -2`):
`919a636` ("docs: working repository migrated to hack-2026-nornikel") changed `.claude/
CLAUDE.md`'s Scope section and `AGENTS.md`'s Key Notes to record the `hack-2026-nornikel`/
`nornikel-kg-search` repository split (see `## Repository Identity And History` above), and
`bb45bce` ("docs: refresh all documentation to the shipped state", current `HEAD`)
rewrote `README.md` (228 lines changed), trimmed `AGENTS.md`'s runtime-defaults section to
state the 32m Nginx limit and full upload-type list directly, updated `.claude/CLAUDE.md`'s
"Validation and deployment notes"/"Known TODOs" sections, and marked
`docs/deployment/fa-nddev.md` as `(HISTORICAL)` with an explicit "legacy stand... NOT
deployed to anymore" banner (all four files verified read at `HEAD` in this sync pass).

One further commit, `4ede8c5` ("feat(qa): natural-language time scopes from question text",
current `HEAD`), added `domain.dates.parse_time_scope` and wired it into
`DemoQAService._effective_filters`/`_apply_scope_to_evidence` so a question's own temporal
phrasing (e.g. «за последние 5 лет») now gates the evidence packet as well as the experiment
table, permissively for derived scopes and strictly for explicit UI filters — see
`mem:ARCH-01-EVIDENCE-MVP` and `mem:TECHDEBT-01-NOW` for the verified detail. `uv run pytest`
now passes **154 tests, 5 skipped** (up from 151), `ruff`/`mypy` clean, and `make eval`'s
`q_year_phrase_is_not_a_filter` case passes via this new permissive-scope path — all
independently live-run verified in this sync pass.

See `mem:ARCH-01-EVIDENCE-MVP`, `mem:DATA-01-EVIDENCE-LEDGER`, `mem:TECHDEBT-01-NOW` for the
per-module detail of each change.

`uv run pytest` passes **182 tests, 5 skipped** at `ee84a6b` (live-run verified in this sync
pass, up from 154 passed / 5 skipped at `4ede8c5`); `uv run ruff check .` passes clean
("All checks passed!") and `uv run mypy` passes clean ("Success: no issues found in 79 source
files") — both live-run verified in this sync pass.

## Frontend Redesign (2026-07-04, HEAD `8d10cc4`)

Four commits after `ee84a6b` (`6eca379`, `f91b90c`, `c468df8`, `d644575`, `8d10cc4`) replaced the
six-section state-nav SPA with a `react-router-dom` v7 multi-page app: `App.tsx` now routes `/`,
`/search`, `/graph`, `/data`, `/analytics`, `/compare`, `/experts`, `/eval`, `/security`, `/demo`
under a shared `AppLayout` (new `widgets/app-layout/`: top `Header` with logo + team badge +
`nav.ts`-driven section nav + live-model badge, and a global `Footer` CTA); the old
`pages/workbench/` was deleted. Design tokens were rebuilt in `shared/config/theme/theme.css`
(blue primary + teal/violet accents, entity-type color tokens, `Inter` font); new pages
`landing` (`/`), `demo` (`/demo`, jury cockpit), `experts`, `compare` were added, and
`AnalysisWorkbench.tsx` was reordered question-first with filters collapsed into a
`<details>` block. Brand assets live in `apps/web/public/brand/` (2.7MB); the 56MB mockup
package `nauchny_klubok_site_package/` that the redesign was built from is now gitignored
(`8d10cc4`) but kept on disk. `cd apps/web && npm run typecheck`/`npm run build` both pass clean
(re-verified in this sync pass); the live stand `https://nornikel.nddev.asia` serves `/` and
`/demo`. Full verified module-level detail: `mem:ARCH-01-EVIDENCE-MVP`'s "Frontend Redesign"
section. Known gap: `/security` is not listed in `shared/config/nav.ts`'s `NAV_ITEMS` (see
`mem:TECHDEBT-01-NOW`).

## Wave 10 — Real-Corpus Audit Response (2026-07-04, HEAD `ee84a6b`)

Thirteen commits (`a2a8908`..`ee84a6b`, see `git log --oneline 42ca7ba..HEAD`) closed the
real-corpus MVP gaps recorded in `.serena/plans/10_AUDIT_RESPONSE_PLAN.md` (Wave 10 plan,
`68bf940`) and its "Implementation status" section (`ee84a6b`). Verified against the working
tree at `HEAD`:

- `services/runtime.py:49` — `SEED_SYNTHETIC_FIXTURE` now defaults to `"false"` (was `"true"`),
  so the demo Ni-Cu fixture is no longer seeded on top of a real corpus by default;
  `scripts/run_eval.py`, `tests/integration/test_api.py`, `test_analytics_api.py`, and
  `tests/unit/test_runtime_paths.py` opt in explicitly; `.env.example:16` is `false`.
- `src/nornikel_kg/services/archive_expansion.py` preserves each archive member's inner
  directory path with a collision-free target instead of flattening to basenames (the
  zip-slip guard is unchanged).
- `src/nornikel_kg/domain/encoding.py` (new) — `decode_text_bytes` tries
  `utf-8-sig`/`utf-8`/`cp1251` then `charset_normalizer`, then a lossy UTF-8 replace; used by CSV
  parsing so CP1251-encoded corpus files no longer fail ingest. `adapters/spreadsheet/parser.py`
  caps (`MAX_SHEETS`/`MAX_ROWS_PER_SHEET`/`MAX_COLUMNS`) are raised to 50/5000/60 and
  env-overridable (`INGEST_XLSX_MAX_SHEETS`/`_MAX_ROWS`/`_MAX_COLUMNS` in `.env.example`).
- `src/nornikel_kg/ports/parser.py` — `ParsedTable`/`ParsedTableRow`/`ParsedTableCell` gained a
  `header` field; spreadsheet and Docling parsers populate it so a row's `text` is
  header-labeled (e.g. "Сульфаты, мг/л: 300"). New `src/nornikel_kg/domain/table_facts.py`
  (`extract_facts_from_row`/`NumericFact`) turns headered rows (wide or tall layout, unit
  parsed from the header) into subject-tagged numeric facts.
- `src/nornikel_kg/domain/quantities.py` — `NumericConstraint` gained a `subject: str = ""`
  field; `parse_parameter_constraints` binds each numeric bound to the analyte/parameter
  subjects named in the question text (сульфаты/хлориды/Ca/Mg/Na/сухой остаток/etc.);
  `facts_satisfy_constraints` matches by subject when the constraint carries one, else by unit
  only. `src/nornikel_kg/services/qa_service.py:_drop_constraint_violating_evidence` removes
  evidence spans whose own facts violate a bound constraint before answer assembly.
- `src/nornikel_kg/domain/extraction.py` — `ENTITY_TYPES`/`RELATION_TYPES` extended with case
  vocabulary: entity types `process`, `condition`, `facility`, `experiment`, `method`, `expert`,
  `organization`, `location`, plus (per the plan doc) `technology_solution`/
  `economic_indicator`/`recommendation`/`limitation`/`patent`/`standard`; relation types
  `USES_MATERIAL`, `OPERATES_AT_CONDITION`, `HAS_ECONOMIC_INDICATOR`, `PRODUCES_OUTPUT`,
  `SHOWS_EFFECT`, `EXPERT_IN`, `MEMBER_OF`, plus (per the plan doc)
  `VALIDATED_BY`/`HAS_LIMITATION`/`RECOMMENDED_FOR`/`SIMILAR_TO`. The extraction prompt was
  updated accordingly; the stand's graph was re-enriched on `deepseek-v4-flash` with the new
  vocabulary live (per `.serena/plans/10_AUDIT_RESPONSE_PLAN.md`'s "Implementation status"
  section, an operational report, not a tracked graph-export artifact): `process` 317,
  `facility` 54, `organization` 83, `location` 67, `economic_indicator` 47, `expert` 79;
  `USES_MATERIAL` 269, `OPERATES_AT_CONDITION` 225, `HAS_ECONOMIC_INDICATOR` 43 — see
  `mem:DATA-01-EVIDENCE-LEDGER` for the fuller entity/relation count.
- UI: `apps/web/src/shared/api/types.ts`'s `EvidenceSpan` gained a `locator: Record<string,
  unknown>` field; `AnalysisWorkbench.tsx` assigns a stable per-answer citation number to each
  cited span (`citationIndex`) and renders numbered `citation-chip` elements plus a
  `citation-verified` badge per sentence (click scrolls to and highlights the evidence card);
  `services/api/routes/health.py`'s `GET /health` now returns `llm_enabled`/`answer_model`/
  `extraction_model`/`embedding_backend`; `WorkbenchPage.tsx` renders the live `health.
  answer_model` instead of a hardcoded model name. `apps/web/src/pages/data/ui/DataPage.tsx`
  renders `stats.quarantine_reasons` (machine-readable quarantine reason codes, see below).
- `src/nornikel_kg/services/ingestion_service.py:_quarantine` now takes a `reason_code`
  (`no_text_layer_ocr_disabled`/`parser_error`/`unexpected_error`), stored as `"[code] msg"` in
  `ingestion_runs.error`; `DuckDBLedgerRepository.corpus_stats()` aggregates
  `quarantine_reasons`/`quarantined` counters from it.
- `src/nornikel_kg/adapters/trafilatura/fetcher.py:assert_public_url` (new) rejects
  non-http(s) schemes and private/loopback/link-local/reserved/metadata-range hosts before
  `UrlFetcherPort.fetch`/`import-url` resolves a URL (SSRF guard).
- `src/nornikel_kg/domain/geography.py` (new) — `detect_geography(head_text)` returns
  `ru`/`foreign`/`mixed`/`None` from explicit RU/foreign country-organization-location signal
  lists, falling back to the Cyrillic-vs-Latin script ratio only when neither side is named;
  `IngestionService` uses it instead of the previous pure-script heuristic.
- The orphaned `GET /graph/demo-path` route was removed from `services/api/routes/graph.py`
  (verified absent at `HEAD`).
- `scripts/run_realcase_eval.py` (new, `make eval-realcase`) hits a live API with the four
  hackathon track questions and asserts citation coverage 1.0 / zero fabrication / zero
  synthetic-Ni-Cu leakage; reported live run: status ok, citation 1.0, 0 fabrication, 0
  synthetic leak (per `.serena/plans/10_AUDIT_RESPONSE_PLAN.md`, not re-run in this sync pass
  since it requires a live stand).
- Stand cleanup (reported in `.serena/plans/10_AUDIT_RESPONSE_PLAN.md`'s T1.1 status, not
  independently re-verified from this repository): the seeded synthetic source plus 16
  `synthetic_v2` fixtures were deleted from the stand ledger, leaving 49 real sources and zero
  synthetic measurements.
- `.serena/plans/10_AUDIT_RESPONSE_PLAN.md` (new, `68bf940`/`ee84a6b`) records the audit
  verdicts and, in its "Implementation status" section, which items were shipped versus
  deliberately deferred: T2.5 (strict question-time scope, locked by the
  `q_year_phrase_is_not_a_filter` eval case), T2.6 (semantic/NLI answer-support check, latency
  cost), T2.8 (LLM-settings rename, cosmetic), T2.2 (archive upload via the API route, batch
  path already covers it), and T3's remaining dead-code items (only the orphaned
  `/graph/demo-path` route was removed).
- Deferred/known at `HEAD`: table headers (`ParsedTable.header`) and geography detection apply
  only to newly ingested sources — existing stand spans keep their prior header/geography
  values until re-ingested (re-enrichment does not re-parse). A real-corpus gold eval set is
  still absent (`scripts/run_eval.py`'s 17 questions still run only against the synthetic
  fixture; `scripts/run_realcase_eval.py` checks 4 live track questions but asserts honesty
  properties, not a gold-answer set).

## Contracts And Data

Full flow: React/Vite multi-page app (react-router-dom v7, ten routes under `AppLayout`) ->
FastAPI (`/sources/upload`,
`/sources/import-url`, `/sources/{id}/enrich`, `/sources/reindex-all`, `/qa/ask`,
`/entities/search`, `/entities/by-type`, `/entities/{id}`, `/graph/neighborhood`, `/graph/timeline`, `/gaps/analyze`,
`/eval/summary`, `/stats/overview`, `/stats/answer-runs`) -> DuckDB-backed evidence ledger +
entity/relation graph -> optional Qdrant hybrid retrieval (dense via `EMBEDDING_BACKEND=local|
yandex|fake`, BM25 sparse always local, optional cross-encoder rerank) -> deterministic-or-LLM
answer synthesis -> claim verification (citation coverage + numeric-mismatch gate) ->
answer-run persistence, cached per `data_version`.

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
- `tenacity` must stay a hard main dependency (`pyproject.toml`); litellm's retry path imports it
  lazily and fails hard without it.

## Change Rules

Update this index whenever a new durable memory is added, renamed, split, or deleted.

## Verification

- `make ci`: verifies backend ruff/mypy/pytest and frontend typecheck/build.
- `make eval`: runs `scripts/run_eval.py` (17 hardcoded `EVAL_QUESTIONS`, incl. numeric-constraint,
  conflict-surfacing, and adversarial prompt-injection cases).
- `docker compose config`: verifies Compose syntax without requiring local secrets.
- `uv run pytest`: 182 tests pass, 5 skipped at `ee84a6b` (live-run verified in this sync pass,
  up from 154 passed / 5 skipped).
- `uv run ruff check .` / `uv run mypy`: both clean at `ee84a6b` (live-run verified, ruff "All
  checks passed!", mypy "Success: no issues found in 79 source files").

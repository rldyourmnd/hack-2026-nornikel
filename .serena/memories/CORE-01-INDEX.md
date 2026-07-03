<!-- Memory Metadata
Last updated: 2026-07-04\nLast commit: bb45bce docs: refresh all documentation to the shipped state
Scope: README.md; apps/web/; services/api/; src/nornikel_kg/; eval/; sample_docs/; scripts/;
  tests/; docker-compose.yml; .github/workflows/ci.yml; .env.example; pyproject.toml;
  .serena/plans/; .serena/reviews/; docs/deployment/; .gitignore
Area: CORE
-->

# CORE-01-INDEX

## Purpose

Index the durable project knowledge for the Nornikel Materials KG Search hackathon MVP.

## Source Of Truth

- `README.md`: repository overview, quick start, demo scenario, and implemented scope.
- `AGENTS.md`: Codex-native project instructions and plugin/tooling policy.
- `.claude/CLAUDE.md`: Claude Code project memory and operational commands.
- `apps/web/`: React/Vite workbench, now a six-section SPA (`apps/web/src/pages/`:
  `workbench`, `graph`, `data`, `analytics`, `eval`, `security`).
- `services/api/`: FastAPI route layer, now including `services/api/routes/stats.py`.
- `src/nornikel_kg/`: backend domain, ports, adapters, and application services.
- `scripts/ingest_corpus.py`: batch-ingests a real document corpus directory into the ledger
  inside the API container; fails fast at start if the ledger cannot be opened (mutually
  exclusive with a running `api` container — see `mem:RELEASE-01-VALIDATION`).
- `eval/`: legacy YAML gold/adversarial fixtures; not read by any code path (`mem:TEST-01-EVALUATION-GATES`).
- `sample_docs/synthetic/`: original P0 fixture. `sample_docs/synthetic_v2/`: W5 17-source synthetic corpus with `manifest.json`.
- `tests/`: unit and integration tests (151 passed, 5 skipped at `652317e`, live-run verified).
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
  (live model bench on a real packet, 2026-07-04: `aliceai-llm` stays the answer model — 6-11s,
  perfect citation discipline; `gpt-oss-120b` synthesized factors best but ran 26-91s live, too
  slow for interactive use; see `mem:TECHDEBT-01-NOW` for the full bench).
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

See `mem:ARCH-01-EVIDENCE-MVP`, `mem:DATA-01-EVIDENCE-LEDGER`, `mem:TECHDEBT-01-NOW` for the
per-module detail of each change.

`uv run pytest` passes **151 tests, 5 skipped** at `652317e` (verified by a live run in this sync
pass, up from 148 passed / 5 skipped); `uv run ruff check .` and `uv run mypy` both pass clean
(also verified live in this sync pass, mypy: "no issues found in 76 source files").

## Contracts And Data

Full flow: React/Vite workbench (six sections) -> FastAPI (`/sources/upload`,
`/sources/import-url`, `/sources/{id}/enrich`, `/sources/reindex-all`, `/qa/ask`,
`/entities/search`, `/entities/{id}`, `/graph/neighborhood`, `/graph/timeline`, `/gaps/analyze`,
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
- `uv run pytest`: 151 tests pass, 5 skipped at `652317e` (live-run verified).
- `uv run ruff check .` / `uv run mypy`: both clean at `652317e` (live-run verified, mypy: "no
  issues found in 76 source files").

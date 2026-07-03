<!-- Memory Metadata
Last updated: 2026-07-04
Last commit: 42ca7ba config: extraction also on deepseek-v4-flash; graph rebuilt
Scope: Makefile; .github/workflows/ci.yml; docker-compose.yml; docs/deployment/nornikel-nddev.md;
  pyproject.toml; services/api/Dockerfile; apps/web/nginx.conf; .env.example; apps/web/;
  services/api/; scripts/ingest_corpus.py; .serena/plans/09_ACCURACY_SOTA_OVERHAUL.md
Area: RELEASE
-->

# RELEASE-01-VALIDATION

## Purpose

Capture the current validation and rollout contract after the accuracy/SOTA overhaul (waves
A-D) and the archive/legacy-format ingestion wave (E).

## Source Of Truth

- `Makefile`: local quality-gate commands (`ci`, `eval`, `reindex`, `warmup`).
- `.github/workflows/ci.yml`: pull-request and `main` CI checks.
- `docker-compose.yml`: local/server container topology (`api`, `web`, `qdrant`).
- `services/api/Dockerfile`: uv-based API image build; now also installs `antiword`, `catdoc`,
  `libarchive-tools` (bsdtar) alongside the existing Docling vision-stack libraries.
- `apps/web/nginx.conf`: bundled web proxy config, `client_max_body_size 32m`.
- `docs/deployment/nornikel-nddev.md`: primary live-stand deployment contract, now documenting
  the DuckDB lock contract and archive-aware batch-ingest procedure.
- `README.md`: quick start, demo scenario, and implemented-scope summary.

## Entry Points

- `make ci`: backend and frontend quality gate.
- `make eval`: `scripts/run_eval.py` (17 questions against the synthetic corpus, incl.
  adversarial injection cases).
- `make reindex`: `uv run python scripts/reindex.py` — rebuilds Qdrant collections from DuckDB.
- `make warmup`: `uv run python scripts/warmup.py` — pre-loads embedding/parser models.
- `scripts/ingest_corpus.py --dir <path> [--limit N] [--max-mb N]`: batch-ingests a real corpus
  directory into the ledger inside the `api` container. It now expands `.zip`/multipart-
  `.zip.NNN`/`.rar` archives first, supports `.pdf/.docx/.docm/.doc/.xlsx/.xls/.csv/.md/.txt`,
  counts image files as no-OCR skips, and **fails fast** (`SystemExit`) if
  `get_ledger_repository().migrate()` cannot open the DuckDB file — the script and a running
  `api` container are mutually exclusive because the `api` process holds a persistent DuckDB
  connection (`1db832d`). The documented procedure is `docker compose ... stop api` then
  `docker compose ... run --rm --no-deps -T api python scripts/ingest_corpus.py ...` then
  `docker compose ... up -d`.
- `docker compose config` / `docker compose up --build`: Compose validation and containerized
  run path.
- `.github/workflows/deploy.yml` (new, `9338017`): auto-deploy on push to `main` — SSH-ships the
  tracked tree, rebuilds and restarts `api`/`web`, smoke-checks `/api/health` +
  `/api/stats/overview`; also runnable via `workflow_dispatch`.

## Current Behavior

`uv run pytest` passes **154 tests, 5 skipped** at `4ede8c5` (verified by a live run in this
sync pass, up from 148 passed / 5 skipped at `327f47c`). `uv run ruff check .` and `uv run mypy`
both pass clean (verified live in this sync pass; mypy: "no issues found in 76 source files").

`adapters/llm/gateway.py` and `adapters/embeddings/yandex.py` now share a client-side pacing
module, `adapters/ratelimit.py` (`RateLimiter`/`get_limiter`, `6feff7a`): the LLM path joins a
`"llm-completions"` limiter (`LLMSettings.llm_rps`, code default `5.0`, `.env.example` stand
value `10`) and retries `litellm.RateLimitError` up to 6 times with jittered backoff;
`LLM_MAX_CONCURRENCY`'s stand value is raised to `8` (code default `3`).

`.github/workflows/deploy.yml` (new, `9338017`/PR #19): on every push to `main`, ships the
tracked tree over SSH (`git archive HEAD | ssh ... tar -x`), rebuilds `api`/`web` via
`docker compose -f docker-compose.server.yml`, runs `up -d`, then smoke-checks
`http://127.0.0.1:8080/api/health` and `/api/stats/overview`; secrets `DEPLOY_SSH_KEY`/
`DEPLOY_HOST`/`DEPLOY_USER`; `concurrency: {group: deploy-production, cancel-in-progress: false}`
serializes overlapping deploys. The primary stand domain changed to `https://изи-никель.рф`
(punycode `xn----jtbedbbojo8m.xn--p1ai`, `.env.example`'s `APP_BASE_URL` default), with
`https://nornikel.nddev.asia` kept as a secondary mirror; both `.claude/CLAUDE.md` and
`docs/deployment/nornikel-nddev.md` document the DNS prerequisite (an A record for
`изи-никель.рф`/`www` -> `165.22.203.232`, after which the host's acme-companion issues the TLS
certificate automatically). Whether that A record has actually been created is not stated in
either tracked file and cannot be verified from this repository; treat it as an open
operational item (`mem:TECHDEBT-01-NOW`).

`EMBEDDING_BACKEND` now also accepts `yandex` (`adapters/embeddings/yandex.py`): dense vectors
via the organizer-provided Yandex AI Studio API, offloading the CPU-bound `local` backend's
sentence-transformers inference; `.env.example` documents `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`,
`YANDEX_EMBED_DOC_MODEL`/`YANDEX_EMBED_QUERY_MODEL` (both default `text-embeddings/latest`).
`.claude/CLAUDE.md`/`AGENTS.md` record Yandex AI Studio as the primary LLM provider too
(same OpenAI-compatible LiteLLM gateway, `https://ai.api.cloud.yandex.net/v1`). Both LLM
roles now run on `deepseek-v4-flash` as of `42ca7ba` (owner requirement, verified in `.claude/
CLAUDE.md`/`.env.example` at `HEAD`; superseding the answers-only switch in `f72c7f6`): answers
(richer author/factor detail, ~17s warm) and extraction (0/6 JSON failures isolation-benched,
more relations/span than `aliceai-llm`, ~16s/span — 2.4x slower per span but a cleaner-typed
graph), `LLM_TIMEOUT_S` raised `30`->`60` in `.env.example` to fit both. `aliceai-llm` (native
strict-JSON, 2.4s) stays in the catalog as a fast fallback, not the active path.
`LLM_ANSWER_MODEL`/`LLM_EXTRACTION_MODEL` remain blank in the tracked `.env.example`; the
concrete model strings are only set in the server's untracked `.env` (not verifiable from this
repository). The LLM gateway code itself
(`src/nornikel_kg/adapters/llm/gateway.py`/`settings.py`) is provider-agnostic and unchanged —
the switch is an env-level base-URL/key/model override, with the previous `dataeyes.ai`
configuration kept as a server-side rollback (`.env.bak-dataeyes`, per `.claude/CLAUDE.md`, not
independently verified by this repository sync since it lives outside tracked files).

`apps/web/nginx.conf` still sets `client_max_body_size 32m` and `proxy_read_timeout 300s` for
`/api/`, unchanged this wave.

`services/api/routes/sources.py` still exposes `POST /sources/{source_id}/enrich` and
`POST /sources/reindex-all`; `DELETE /sources/{source_id}` now also best-effort deletes the
source's Qdrant units via `retrieval.index.delete_source_units` (wrapped in
`contextlib.suppress(Exception)` — index cleanup failure never blocks the delete, since DuckDB
rejoin already guards reads against stale Qdrant points).

Docker Compose defines `api`, `web`, `qdrant`, unchanged topology; `services/api/Dockerfile` now
also installs `antiword`, `catdoc` (legacy `.doc` text extraction) and `libarchive-tools`
(`bsdtar`, `.rar` extraction in the batch corpus ingester) alongside the existing Docling vision
libraries (`libgl1`, `libglib2.0-0`, `libxcb1`, `libxext6`, `libsm6`).

`docs/deployment/nornikel-nddev.md` now documents the DuckDB lock contract explicitly (a
dedicated section) and routes vector reindex through `POST /sources/reindex-all` (the api owns
the lock) instead of a direct `docker compose exec ... scripts/reindex.py`.

`pyproject.toml` gained `json-repair` as a main dependency (LLM gateway JSON repair fallback);
the `ingest` extra gained `optimum[onnxruntime]` (reranker ONNX backend) and `xlrd` (legacy
`.xls` support); mypy overrides added for `json_repair`/`json_repair.*` and `pandas`/`pandas.*`.

**Dual-repo auto-deploy state (verified 2026-07-04, see `mem:CORE-01-INDEX` for full repo
identity note)**: `.github/workflows/deploy.yml` exists in both `origin`
(`rldyourmnd/hack-2026-nornikel`, workflow state `"active"`) and `legacy-origin`
(`rldyourmnd/nornikel-kg-search`, workflow state `"disabled_manually"` — confirmed via `gh
api repos/rldyourmnd/nornikel-kg-search/actions/workflows`). Deploy secrets
(`DEPLOY_SSH_KEY`/`DEPLOY_HOST`/`DEPLOY_USER`) are configured in both repos, but only a push
to `hack-2026-nornikel`'s `main` actually triggers a deploy.

## Contracts And Data

The web container serves the Vite build through Nginx and proxies `/api/` to the FastAPI
container with `client_max_body_size 32m` and `proxy_read_timeout 300s`. `VITE_API_BASE_URL`
defaults to `/api` for container deployment.

The API container sets `PROJECT_ROOT=/app`; `src/nornikel_kg/services/runtime.py` resolves
`data/`, `sample_docs/`, and `data/artifacts` (via `ARTIFACT_ROOT`) relative to that root.

`docs/deployment/nornikel-nddev.md` documents the primary stand: `ssh curestry`
(`165.22.203.232`, 8 vCPU / 31 GiB), TLS terminated by the host-wide `curestry-nginx-1`
(nginx-proxy + acme-companion), `api`/`qdrant` internal-only while `api` also joins the external
`lf-net` network to reach the co-located `/srv/langfuse` self-hosted Langfuse v3 stack.

`DuckDBLedgerRepository._connect()` still holds one persistent DuckDB connection behind a class
`RLock` (unchanged from `f40ab72`); the API process holds the DuckDB file lock for its lifetime,
so container-level diagnostics (e.g. a `docker exec` DuckDB CLI session against
`data/catalog.duckdb`) cannot open the file directly while the `api` service is running —
`scripts/ingest_corpus.py` now enforces this contract with an explicit fail-fast check instead
of relying on operator memory.

## Invariants

- Do not commit `.env`, browser artifacts, `.playwright-cli/`, `.venv/`, node_modules, or DuckDB
  runtime files.
- Do not replace `npm ci` in CI/Docker with non-lockfile installs.
- Compose must remain valid without local secrets.
- Keep `MAX_SOURCE_UPLOAD_BYTES` (wherever configured) at or below the active Nginx
  `client_max_body_size` (currently `32m` in `apps/web/nginx.conf`).
- Keep `apps/web/nginx.conf`'s `proxy_read_timeout` long enough for cold Docling/embedding-model
  loads; do not shorten it without confirming the current model warm-up latency.
- Do not call `duckdb.connect(...)` outside `DuckDBLedgerRepository._connect()`; stop the `api`
  container before running `scripts/ingest_corpus.py` or any other direct-file-access tool.

## Change Rules

When changing CI, verify referenced GitHub Action major tags exist. When changing frontend
dependencies, update `apps/web/package-lock.json` and run the frontend build. When changing API
dependencies, update `uv.lock` and run backend tests. When changing `MAX_SOURCE_UPLOAD_BYTES` or
the Nginx body-size limit, keep both the FastAPI code default and `apps/web/nginx.conf`'s
`client_max_body_size` consistent, and check any host-level reverse proxy limit/timeout too.

## Verification

- `make ci`: proves Python lint/type/tests and TypeScript/build; `uv run pytest` verified at 151
  passed / 5 skipped at `652317e` in this sync pass; `ruff`/`mypy` both clean (live-run verified,
  mypy: "no issues found in 76 source files").
- `make eval`: proves the 17-question synthetic-fixture answer/safety metrics (incl. adversarial
  injection cases); does not exercise the real-corpus ontology/scope-filter/reranker behavior
  against real data (see `mem:TECHDEBT-01-NOW`).
- `docker compose config`: proves Compose syntax.
- `git rev-list --left-right --count origin/main...main` -> `0\t0` (verified 2026-07-04 at
  `652317e`, before this sync's own commit): local `main` and `origin/main` were in sync; no
  pending push backlog.

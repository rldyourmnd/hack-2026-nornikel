# Claude Project Notes

## Scope
Repository: `hack-2026-nornikel` (working repo; `nornikel-kg-search` is the
frozen pre-migration archive, do not push there)
Owner workflow: rldyour plugins/skills.

## Project state (verified)
- P0 backend is a deterministic evidence-led QA system built on DuckDB.
- Sources: `src/nornikel_kg/`; API routes: `services/api/routes/`; frontend: `apps/web/`
  (react-router multi-page: AppLayout header/footer shell + landing `/` and
  jury demo `/demo`; design tokens + brand assets in `public/brand/`;
  mockup source in `nauchny_klubok_site_package/`, kept out of the web build).
- `make ci`, `make eval` and browser/ deploy smoke are used for validation.
- Memory/invariant source-of-truth is `.serena/memories/`.
- MVP upgrade plan (2026-07-02, entry point `.serena/plans/00_PLAN_INDEX.md`): waves W0-W5
  in `.serena/plans/`, self-critique and source-backed facts in `.serena/reviews/`.
  Plans amend `.serena/newproj/nornikel-kg-search/18_IMPLEMENTATION_SPEC.md`.

## LLM Constraints (hackathon rules)
- **2026-07-04 REALITY: the organizer Yandex key is DENIED (403 for both LLM and
  embeddings).** Working stand stack = **dataeyes** LLM (`openai/gpt-5.4-mini`
  extraction + `openai/gpt-5.5` answers) + **`EMBEDDING_BACKEND=openai`** (dense via
  dataeyes `/embeddings`, `text-embedding-3-small` 1536-dim, `QDRANT_COLLECTION=evidence_oai`).
  The gateway is dual-provider with failover on any error. Set `JURY_ALLOWED_LABELS`
  on the stand (visibility floor). Yandex block below is the intended-but-currently-blocked
  config; see `.serena/memories/hackathon-llm-constraints` + `docs/deployment/full-ingest-runbook.md`.
- **Primary provider (2026-07-03): Yandex AI Studio, organizer-provided** (API key +
  folder, no spend limits) — OpenAI-compatible base `https://ai.api.cloud.yandex.net/v1`
  through the LiteLLM SDK. Stand models (2026-07-04): `deepseek-v4-flash` for
  BOTH answers and extraction (owner requirement; re-benched through the real
  gateway — json_repair recovers its non-native JSON, 0 JSON failures, 4/4
  verified answers, richer detail; ~16-17s per call so `LLM_TIMEOUT_S=60`).
  The full corpus graph was rebuilt clean on DeepSeek (2026-07-04): 3107
  entities / 6771 relations with a tight R&D ontology (material/property/regime/
  value/person/equipment/publication) — leaner than the prior aliceai graph
  (4206/16560) because alice emitted a noisy 100+-type tail; connectivity is
  strong (e.g. «Медный штейн»: 154 evidence spans, 111 typed edges —
  HAS_MEASUREMENT/APPLIES_REGIME/DESCRIBED_IN/MADE_OF/USED_EQUIPMENT). Catalog
  also hosts aliceai-llm (native strict-JSON 2.4s, fast fallback), qwen3-235b,
  gpt-oss, yandexgpt-5-pro.
  Dense embeddings: `emb://<folder>/text-embeddings/latest` (1536-dim) via
  `EMBEDDING_BACKEND=yandex`; sparse BM25 stays local. Embedding quota 10 RPS
  (raisable via support ticket).
- Previous provider (dataeyes.ai + gpt-5.4-mini, organizer-approved) is preserved in
  the server's `.env.bak-dataeyes` — rollback is an env swap.
- CI never needs LLM secrets or network: all LLM paths must keep deterministic fakes;
  `EMBEDDING_BACKEND=fake|local` keeps retrieval offline-testable.

## Durable Commands
- Backend checks: `uv run ruff check .`, `uv run mypy`, `uv run pytest`.
- Frontend checks: `cd apps/web && npm run lint`, `npm run typecheck`, `npm run build`.
- Combined smoke: `make ci` and `make eval`.

## Branch / Git
- Pushes go through feature branches and PR merge to `main`.
- `main...origin/main` should remain clean and synced.
- Auto-deploy: every push to `main` triggers `.github/workflows/deploy.yml`
  (SSH deploy to the stand + smoke); secrets `DEPLOY_SSH_KEY/HOST/USER`.

## Runtime Paths
- DuckDB path defaults to `data/catalog.duckdb`.
- Synthetic fixture path defaults to `sample_docs/synthetic`.

## Validation and deployment notes
- Primary stand: `https://изи-никель.рф` (punycode `xn----jtbedbbojo8m.xn--p1ai`;
  DNS delegation pending on the owner side — the cert auto-issues once A records
  exist); mirror: `https://nornikel.nddev.asia`. Host `ssh curestry` (compose
  project `/srv/nornikel-kg-search`; TLS via host nginx-proxy + acme-companion;
  Langfuse v3 in `/srv/langfuse` over the external `lf-net` network). Deploy
  contract: `docs/deployment/nornikel-nddev.md`.
- Do not leave local runtime artifacts (temp DBs, browser artifacts, runtime markers).
- Upload hardening contract: `POST /sources/upload` accepts `.csv .md .markdown
  .txt .text .pdf .docx .docm .doc .xlsx .xls` with MIME checks and
  `MAX_SOURCE_UPLOAD_BYTES` (default `5242880`; `26214400` on the server);
  `POST /sources/import-url` ingests online resources via trafilatura; archives
  (.zip / multipart .zip.001 / .rar) go through `scripts/ingest_corpus.py`.
- The bundled web Nginx proxy sets `client_max_body_size 32m` and 300s `/api/`
  proxy timeouts; the per-vhost limit on the server is 30m.
- DuckDB lock contract: the api process holds one persistent connection — batch
  tools (`ingest_corpus.py`, `run_eval.py --store`) need an api-stop window.
- Error details from API failures are surfaced to the UI through shared API client (`apps/web/src/shared/api/client.ts`).

## Known TODOs / P1
- Real-corpus gold eval set (the 17 eval questions run on the synthetic fixture).
- Geomechanics ontology coverage; CI runs without the `ingest` extra
  (GLiNER/Docling/spreadsheet paths untested in CI); one non-standard `.docm`
  quarantines under the Docling backend.
- Owner-side: DNS A records for `изи-никель.рф` → 165.22.203.232; support
  ticket to raise the Yandex embeddings quota (10 RPS); reissue the Yandex API
  key after the hackathon (it appeared in chat).

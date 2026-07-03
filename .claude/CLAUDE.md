# Claude Project Notes

## Scope
Repository: `nornikel-hackathon`
Owner workflow: rldyour plugins/skills.

## Project state (verified)
- P0 backend is a deterministic evidence-led QA system built on DuckDB.
- Sources: `src/nornikel_kg/`; API routes: `services/api/routes/`; frontend: `apps/web/`.
- `make ci`, `make eval` and browser/ deploy smoke are used for validation.
- Memory/invariant source-of-truth is `.serena/memories/`.
- MVP upgrade plan (2026-07-02, entry point `.serena/plans/00_PLAN_INDEX.md`): waves W0-W5
  in `.serena/plans/`, self-critique and source-backed facts in `.serena/reviews/`.
  Plans amend `.serena/newproj/nornikel-kg-search/18_IMPLEMENTATION_SPEC.md`.

## LLM Constraints (hackathon rules)
- **Primary provider (2026-07-03): Yandex AI Studio, organizer-provided** (API key +
  folder, no spend limits) — OpenAI-compatible base `https://ai.api.cloud.yandex.net/v1`
  through the LiteLLM SDK. Stand models: `aliceai-llm` for extraction AND answers
  (live-benched: strict-JSON extraction 2.4s, best RU quality; catalog also hosts
  open-weight qwen3-235b/deepseek-v4-flash/gpt-oss as fallbacks). Dense embeddings:
  `emb://<folder>/text-embeddings/latest` (1536-dim) via `EMBEDDING_BACKEND=yandex`;
  sparse BM25 stays local. Embedding quota 10 RPS (raisable via support ticket).
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
- Primary stand: `https://изи-никель.рф` (punycode `xn----jtbedbbojo8m.xn--p1ai`);
  mirror: `https://nornikel.nddev.asia` (secondary). Host `ssh curestry` (compose project
  `/srv/nornikel-kg-search`; TLS via host nginx-proxy + acme-companion; Langfuse v3 in
  `/srv/langfuse` reachable over the external `lf-net` network). Deploy contract:
  `docs/deployment/nornikel-nddev.md`. Interim mirror: `fa.nddev.asia`
  (`docs/deployment/fa-nddev.md`).
- Do not leave local runtime artifacts (temp DBs, browser artifacts, runtime markers).
- Upload hardening contract: `POST /sources/upload` accepts `.csv`, `.md`, `.markdown`,
  `.txt`, `.text`, `.pdf`, `.docx` with MIME checks and `MAX_SOURCE_UPLOAD_BYTES`
  (default `5242880`; `26214400` on the server) size limit; `POST /sources/import-url`
  ingests online resources via trafilatura.
- The bundled web Nginx proxy sets `client_max_body_size 6m` and 300s `/api/` proxy
  timeouts; the per-vhost limit on the server is 30m.
- Error details from API failures are surfaced to the UI through shared API client (`apps/web/src/shared/api/client.ts`).

## Known TODOs / P1
- Planned in `.serena/plans/03_IMPLEMENTATION_PLAN.md` (W1-W3): Docling PDF/DOCX ingest
  (text layer only, no OCR), LiteLLM extraction + answer synthesis, Qdrant hybrid retrieval,
  own graph layer (entities/relations in DuckDB + NetworkX), gaps/conflicts, graph UI.
- Deployment moves to a new server before the deadline (~2026-07-16); `fa.nddev.asia`
  is the interim stand. See `.serena/plans/06_DEPLOYMENT_AND_OBSERVABILITY.md`.

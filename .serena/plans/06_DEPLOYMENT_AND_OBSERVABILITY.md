# Deployment And Observability

Date: 2026-07-02
Status: planned (new server rollout in W5; fa.nddev.asia remains the interim stand)

## Purpose

Topology, environment matrix, Langfuse observability, and migration steps for the
new (more powerful) server. Final public URL is owner-provided later; nothing below
hardcodes the domain.

## Topology (new server)

Two separate Docker Compose projects (isolation: app redeploys never touch
observability data):

```text
app stack (repo docker-compose.yml + server override)
  web      nginx + React build, proxies /api/ (client_max_body_size >= upload limit)
  api      FastAPI; PROJECT_ROOT=/app; ingest extra installed; HF cache volume
  qdrant   vector store, internal-only
  ollama   OPTIONAL fallback profile (compose profile "fallback"); models volume

langfuse stack (official docker-compose from langfuse repo, pinned v3.x)
  langfuse-web + langfuse-worker + postgres + clickhouse + redis + minio
  requirement: >= 4 vCPU / 8 GB RAM headroom for this stack alone
```

Volumes: `data/` (DuckDB + artifacts + HF cache), `qdrant_storage`, `ollama_models`,
langfuse stack volumes (postgres/clickhouse/minio). Host nginx terminates TLS and
proxies to the app `web` (same pattern as `docs/deployment/fa-nddev.md`); Langfuse UI
exposed on a separate internal/basic-auth vhost — it is an operator tool, not part of
the public demo surface.

## Environment Matrix

| Variable | Default / example | Notes |
| --- | --- | --- |
| `LLM_ENABLED` | `true` on server, `false` in CI/tests | master switch to deterministic mode |
| `DATAEYES_API_BASE` | `https://api.dataeyes.ai/v1` | confirm exact path in W0 discovery (`/v1` vs root) |
| `DATAEYES_API_KEY` | server secret | never in git; owner-provided |
| `LLM_EXTRACTION_MODEL` | `openai/<small-open-weight-id>` | LiteLLM string against DATAEYES base; chosen in W0 (small DeepSeek/Qwen/GLM-class with verified open weights) |
| `LLM_ANSWER_MODEL` | `openai/<open-weight-id>` | same policy; may equal extraction model |
| `LLM_TIMEOUT_S` / `LLM_MAX_RETRIES` | `30` / `1` | gateway guards |
| `LLM_MAX_CONCURRENCY` | `3` | protects stand + provider limits |
| `EMBEDDING_BACKEND` | `local` | `local` = sentence-transformers; `api` only if discovery finds open-weight embeddings |
| `EMBEDDING_MODEL_ID` | `deepvk/USER-bge-m3` | 1024-dim dense |
| `SPARSE_MODEL_ID` | `Qdrant/bm25` | fastembed |
| `HF_HOME` | `/app/data/hf-cache` | Docling + GLiNER + embeddings model cache (volume) |
| `QDRANT_URL` / `QDRANT_COLLECTION` | `http://qdrant:6333` / `evidence_units` | existing |
| `OLLAMA_BASE_URL` | `http://ollama:11434` (profile only) | fallback route `ollama_chat/qwen3:4b` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | server secrets | from self-hosted Langfuse project |
| `LANGFUSE_HOST` | `http://<langfuse-web>:3000` (internal) | SDK v2 callback target |
| `MAX_SOURCE_UPLOAD_BYTES` | `26214400` (25 MiB) | raised for PDFs; nginx layers must exceed it |
| `DUCKDB_PATH` / `ARTIFACT_ROOT` / `SYNTHETIC_SAMPLE_DIR` | existing defaults | unchanged |

`.env.example` gets exactly this matrix with placeholders (W0 doc amendment).

## Provider Discovery Protocol (W0, first hour with the key)

```bash
curl -sS $DATAEYES_API_BASE/models -H "Authorization: Bearer $DATAEYES_API_KEY"   # try /v1/models and /models
# pick open-weight candidates -> verify weights on HF (exact version!) -> smoke:
curl -sS $DATAEYES_API_BASE/chat/completions -H "Authorization: Bearer $KEY" -d '{
  "model": "<candidate>", "temperature": 0,
  "response_format": {"type": "json_schema", "json_schema": {...}},
  "messages": [{"role":"user","content":"Извлеки материал и свойство: ..."}]}'
curl -sS $DATAEYES_API_BASE/embeddings -d '{"model":"<emb?>","input":"тест"}'      # existence check only
```

Record results (catalog table, latency, RU quality notes, json_schema support) in
this file under "Discovery Results" and pick model IDs.

### Discovery Results (2026-07-03, working key — COMPLETE)

- The second owner key works against `https://platform.dataeyes.ai/v1`. Catalog:
  **180 models** (GPT-4/5.x, DeepSeek v3/v4, Qwen 3.5–3.7, GLM 4.7–5.2, Kimi K2.x,
  MiniMax, embeddings `text-embedding-3-*`).
- RU guided-JSON smoke (temperature 0): `gpt-5.4-mini` — 2 s, clean JSON (needs
  `additionalProperties:false`, handled by gateway `_strictify`); `deepseek-v3.2-251201`
  — 7 s, clean RU JSON, **best open-weight candidate** (weights on HF);
  `qwen3.5-27b` — returned array (schema not enforced); `glm-4.7` — 18 s / 834
  completion tokens (thinking); `Moonshot-Kimi-K2-Instruct` — requires "json" in
  messages. Providers do NOT reliably enforce `json_schema` → prompts carry the
  format inline and invalid payloads get one reminder regeneration.
- **Configured: `openai/gpt-5.4-mini`** for extraction and answers;
  `LLM_ENABLED=true` on the stand since 2026-07-03.
  **Organizers approved this model for the team (owner confirmation, 2026-07-03)**
  — the mandatory pre-freeze swap is withdrawn. `deepseek-v3.2-251201` (verified
  open weights, 7 s clean RU JSON in smoke) stays the documented fallback if the
  approval changes; switching is a one-line `.env` edit.
- Embeddings stay local (`deepvk/USER-bge-m3`); catalog embeddings are
  OpenAI-proprietary and irrelevant.

### Prior attempt (2026-07-02, partial — first key invalid)

- Correct LLM base URL is `https://platform.dataeyes.ai/v1` (unified global endpoint,
  Bearer auth). `https://api.dataeyes.ai` is a separate Search & Reader product with
  its own key — the `DATAEYES_API_BASE` default above is superseded.
- The first owner-provided key was rejected by every endpoint
  (`无效的令牌` on platform.dataeyes.ai / platform.shuyanai.com, `Invalid api key`
  on api.shuyanai.com). Likely causes: key issued for the Search & Reader product,
  not activated, or no balance. A new key from the "AI Models" console section is
  required; catalog listing, json_schema smoke, and the model matrix remain blocked.
- **Interim dev decision (owner, 2026-07-02):** `LLM_EXTRACTION_MODEL` and
  `LLM_ANSWER_MODEL` are set to `openai/gpt-5.5-mini` in the server `.env` for
  development only (`LLM_ENABLED=false` until a working key exists). This violates
  the track's open-weight rule and MUST be replaced with a verified open-weight
  model before demo freeze; the weights-openness gate in
  `01_MVP_SCOPE_AND_DECISIONS.md` still applies to the final configuration. Known catalog snapshot
(public site, 2026-07-02): open-weight-class entries DeepSeek V4 Pro, GLM 5.2,
Kimi K2.7, MiniMax M3, ByteDance Seed 2.0; proprietary entries (GPT-5.5, Claude
Opus 4.8, Gemini, Grok) are present in the same catalog and are FORBIDDEN for this
project. "Qwen 3.7 Max" requires a weights check before use (Max tier is
historically API-only).

## Observability

- LiteLLM SDK callbacks: `litellm.success_callback = ["langfuse"]` +
  `failure_callback`; `metadata={"trace_id": <run_id>, "tags": ["ingest"|"qa"],
  "session_id": <source_id|question hash>}` — every extraction and answer traceable;
  cost/latency/tokens per run become pitch numbers.
- Pin `langfuse==2.59.*` (SDK v2 callback path documented by LiteLLM; v3 server
  accepts v2 ingestion). If callback breaks against the v3 server in W5 smoke,
  fallback: Langfuse OTEL integration (documented alternative) — decision recorded
  in the critical review, not improvised.
- Structured JSON logs stay primary for non-LLM paths (request_id, source_id,
  run_id, stage, latency, error class).
- App never blocks on Langfuse: callbacks are fire-and-forget; stand works with
  Langfuse down.

## Docker Image Changes (api)

- Install with ingest extra + locked versions (`uv pip install .[ingest]` from lock
  or wheel-based install); BuildKit cache mounts to avoid re-downloading torch.
- Model weights are NOT baked into the image: first-run download into `HF_HOME`
  volume; `make warmup` target pre-pulls Docling/TableFormer + GLiNER + embeddings
  on the server (documented in runbook) so first user request is fast.
- Healthcheck: `/health` extended with component statuses (duckdb, qdrant reachable,
  llm configured true/false) — used by compose healthchecks and the smoke script.

## Migration Steps (fa.nddev.asia -> new server)

1. Provision Docker + compose on the new host; copy server override compose pattern.
2. Deploy langfuse stack; create project; store keys as server secrets.
3. Deploy app stack; `make warmup`; run `make eval-full`; ingest `synthetic_v2`.
4. Point the new domain's nginx vhost (TLS via Let's Encrypt) to app web port.
5. Public smoke: health, ask, upload, graph, gaps; Langfuse trace check.
6. Keep fa.nddev.asia running until the new stand passes smoke twice; then freeze
   old stand (read-only) and update README/links.

## Backups And Stand Safety

- Nightly (cron) tar snapshot: DuckDB file + `data/artifacts` + qdrant snapshot API
  dump -> dated archive; restore drill once in W5.
- Rate limiting: LLM concurrency cap in-app; nginx basic rate limit on `/api/qa/ask`
  (stand protection during judging).
- Rollback: previous app image tag kept; `docker compose up -d --no-deps api` with
  prior tag is the documented rollback path.

# Научный клубок — R&D Knowledge Graph (Nornikel Hackathon 2026)

Evidence-first knowledge graph and QA system for mining-and-metallurgy R&D.

The product promise:

> For every answer sentence, show the exact document/span/table row that supports
> it — and never let a number into an answer that does not literally exist in the
> cited evidence.

Live stand: **https://изи-никель.рф** (primary; punycode `xn----jtbedbbojo8m.xn--p1ai`),
mirror **https://nornikel.nddev.asia**. Deployment contract:
`docs/deployment/nornikel-nddev.md`. Every push to `main` auto-deploys via
`.github/workflows/deploy.yml`.

## What the system does

- **Ingest**: PDF/DOCX/DOCM (Docling, text layer only — scans quarantine honestly,
  no OCR), legacy DOC (antiword/catdoc), XLSX/XLS (sheet rows with provenance),
  CSV/Markdown/TXT, web pages (trafilatura), and archives in the batch ingester
  (.zip, multipart .zip.001/.002, .rar via bsdtar). Year + geography metadata per
  source, background enrichment with recoverable run lifecycle.
- **Extract**: word-boundary dictionary scan over a metallurgy ontology,
  GLiNER zero-shot NER (`urchade/gliner_multi-v2.1`, sentence-boundary overlap
  chunking), LLM guided-JSON extraction with typed relations; entity resolution
  ladder exact → alias → semantic (cosine ≥ 0.90 with a digit veto) → create.
  Every source becomes a `publication` node with extracted date and
  `AUTHORED_BY`/`DESCRIBED_IN` edges.
- **Retrieve**: Qdrant hybrid (dense 1536-dim Yandex `text-embeddings` + local
  Russian BM25, RRF fusion), incremental hash-skip indexing, targeted DuckDB
  rejoin — the vector index is never authoritative.
- **Answer**: LLM synthesis (`aliceai-llm` via organizer-provided Yandex AI
  Studio) gated by claim verification: every sentence must cite packet span ids
  AND carry only numbers that literally exist in the cited spans; failed
  synthesis degrades to a deterministic summary, never to unverified text.
  Scoped filters: geography (отечественная/зарубежная), year ranges, and
  unit-canonical numeric constraints («не более 300 мг/л», «от 100 до 300»,
  мг/дм³ ≡ мг/л).
- **Analyze**: data-driven conflict detection (direction/method/unit-aware
  numeric disagreement), material×regime×property gaps matrix, dated decisions
  and publications timeline, graph neighborhoods with expert-aware ranking.
- **Prove**: 17-question offline eval (citation coverage 1.0, zero fabricated
  numbers, prompt-injection resistance, zero label leaks) + stored eval runs
  served to the UI; answer-run audit trail.

UI sections: Поиск, Граф знаний, Данные, Аналитика, Качество, Безопасность.

## Providers and models (organizer-approved)

- **LLM**: Yandex AI Studio (OpenAI-compatible `https://ai.api.cloud.yandex.net/v1`)
  through a single LiteLLM gateway adapter. Stand model `aliceai-llm` for both
  extraction (native strict-JSON, ~2.4s) and answers (~6-11s) — selected by a live
  bench against qwen3-235b / gpt-oss-120b / deepseek-v4-flash / yandexgpt-5-pro.
- **Embeddings**: Yandex `text-embeddings` (1536-dim) via `EMBEDDING_BACKEND=yandex`;
  sparse BM25 stays local so hybrid retrieval keeps an offline lexical leg.
- **Quota discipline**: process-wide client-side queues pace requests under the
  documented quotas (10 RPS embeddings, 10 concurrent generations) with
  429-aware backoff — see `src/nornikel_kg/adapters/ratelimit.py`.
- `LLM_ENABLED=false` + `EMBEDDING_BACKEND=fake|local` keep every pipeline
  deterministic and offline — the default for CI and the demo safety net.
  The previous provider config (dataeyes.ai) is preserved server-side as backup.

## Quick Start

Requirements: Python 3.12, uv, Node 24, Docker Compose (optional).

```bash
make install          # backend + frontend deps
make api              # FastAPI on :8000 port
cd apps/web && VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Quality gates (all offline, no LLM secrets needed):

```bash
make ci               # ruff + mypy strict + pytest + frontend typecheck/build
make eval             # 17-question deterministic eval incl. adversarial cases
docker compose config
```

## Upload hardening

- `POST /sources/upload` accepts `.csv .md .markdown .txt .text .pdf .docx .docm
  .doc .xlsx .xls` with filename/MIME/size validation
  (`MAX_SOURCE_UPLOAD_BYTES`, default 5 MiB, 25 MiB on the stand).
- The bundled web Nginx allows `client_max_body_size 32m` and 300s `/api/`
  proxy timeouts (first Docling runs download models).
- PDFs without a text layer are quarantined with a visible reason — never a 500.

## Demo scenario

Track-derived questions that showcase the pipeline on the real corpus:

```text
Какие технические решения организации циркуляции католита при
электроэкстракции никеля описаны в практике?        → конкретный насос и расход
Как распределяются драгоценные металлы между штейном и шлаком?
Какие методы обессоливания воды подходят при сульфатах не более 300 мг/л?
```

Every answer returns a grounded Russian summary with confidence, experiment
table (when structured data matches), exact `EvidenceSpan` cards, graph paths,
relevance-gated conflicts, honest gaps, and verification metrics.

## Architecture boundaries

- DuckDB is the system of record (ledger + graph); if DuckDB and Qdrant
  disagree, DuckDB wins. The API process holds one persistent DuckDB
  connection — batch tools and a running API are mutually exclusive
  (see the deployment doc for the lock contract).
- Only `src/nornikel_kg/adapters/llm/gateway.py` may import litellm.
- Domain and services depend on ports; vendor clients live in adapters.
- No secrets in git: copy `.env.example` to `.env` on the runtime host.

## Repository layout

```text
apps/web/          React/Vite workbench (six-section SPA)
services/api/      FastAPI app and routes
src/nornikel_kg/   Domain, services, adapters, resources
sample_docs/       Synthetic corpus (17 sources + manifest)
scripts/           Batch ingest, eval, reindex, corpus generator
tests/             Unit and integration tests (150+)
docs/deployment/   Server deployment notes and lock contract
.serena/           Plans, reviews, and project memories
```

History note: this repository is the working home since 2026-07-03;
`rldyourmnd/nornikel-kg-search` is the frozen pre-migration archive.

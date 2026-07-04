# Научный клубок - Evidence-Led R&D Knowledge Graph

Evidence-first question answering and knowledge-graph workbench for a Russian
mining-and-metallurgy R&D corpus.

The product invariant is simple:

> Every answer sentence must cite the exact source span that supports it. Numeric
> claims are allowed only when the cited evidence contains the same value.

Live stand: **https://изи-никель.рф** (primary; punycode
`xn----jtbedbbojo8m.xn--p1ai`), mirror **https://nornikel.nddev.asia**.
Deployment details live in `docs/deployment/nornikel-nddev.md`.

## Capabilities

- **Ingest real technical corpora**: PDF, DOCX/DOCM, legacy DOC, XLSX/XLS,
  CSV/Markdown/TXT, web pages, and recursive archives. PDF text-layer parsing
  uses a no-GPU pypdfium2 fast path by default; scanned PDFs are quarantined
  honestly instead of being guessed.
- **Build a typed evidence ledger**: source documents, spans, table rows,
  numeric facts, entities, relations, ingestion runs, and answer runs are stored
  in DuckDB with stable identifiers and provenance.
- **Retrieve with hybrid search**: Qdrant stores dense vectors plus sparse BM25
  signals, then results are rejoined to DuckDB before they can be trusted.
- **Extract graph facts**: dictionaries, optional NER, and a configurable
  LiteLLM gateway produce typed entities and relations. The production profile
  is selected by environment variables, so provider and model IDs are not
  hardcoded into the domain layer.
- **Answer with verification**: answer synthesis is gated by citation coverage,
  numeric support, source-label filtering, prompt-injection resistance, and
  contradiction checks. Provider failures degrade to deterministic summaries,
  not unverified text.
- **Analyze the corpus**: graph neighborhoods, material/regime/property gaps,
  conflict signals, source statistics, answer-run verification metrics, and
  real-case evaluation are available through the API and UI.

UI sections: Search, Knowledge Graph, Data, Analytics, Quality, and Security.

## Architecture

```text
apps/web/          React/Vite workbench
services/api/      FastAPI app and routes
src/nornikel_kg/   Domain, services, ports, adapters, resources
scripts/           Batch ingest, reindex, real-case evaluation
tests/             Unit and integration tests
docs/deployment/   Stand deployment and ingest runbooks
.serena/           Maintainer memory
```

Key boundaries:

- DuckDB is the authoritative ledger. Qdrant is a retrieval accelerator only.
- Domain and services depend on ports; vendor clients live in adapters.
- Only `src/nornikel_kg/adapters/llm/gateway.py` imports LiteLLM.
- Runtime secrets stay in `.env` on the host. `.env.example` contains placeholders
  only.
- Production ingest must not require a local GPU or graphical runtime. Remote
  LLM/embedding APIs and text-layer parsers are the supported fast path.

## Quick Start

Requirements: Python 3.12, uv, Node 24, Docker Compose.

```bash
make install
make api
cd apps/web && VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Quality gates:

```bash
make ci
make eval-realcase    # requires a running API
docker compose config
```

`make ci` is offline and deterministic: it does not require provider secrets or
network LLM calls.

## Configuration

Copy `.env.example` to `.env` and set provider credentials on the runtime host.
The main knobs are:

- `LLM_ENABLED`, `LLM_API_BASE`, `LLM_API_KEY`, `LLM_EXTRACTION_MODEL`,
  `LLM_ANSWER_MODEL`
- `LLM_EXTRACTION_MODE=source_packet|span_budget`
- `EMBEDDING_BACKEND=openai|local|fake|yandex`
- `EMBEDDING_API_BASE`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL_ID`
- `QDRANT_COLLECTION`, `QDRANT_ENTITY_COLLECTION`
- `JURY_ALLOWED_LABELS`, `DEFAULT_SOURCE_LABEL`

Use a new Qdrant collection whenever the embedding dimension changes.

## Upload And Security

- `POST /sources/upload` validates filename, extension, MIME, and size.
- `POST /sources/import-url` uses an SSRF-hardened fetcher with redirect-hop
  revalidation and response-size caps.
- Batch archive expansion rejects path traversal, enforces per-member and
  cumulative extraction limits, and preserves archive-member provenance.
- Source labels are filtered before retrieval context reaches the LLM. Requests
  can only narrow the deployment visibility floor.

## Batch Ingest

The recommended production path builds a graph in a separate DuckDB file and
separate Qdrant collections, then swaps them atomically:

```bash
docker compose -f docker-compose.server.yml run --rm --no-deps -T api \
  python scripts/ingest_corpus.py --dir DATA_HACK --sample 300 --workers 6 --max-mb 150
```

See `docs/deployment/full-ingest-runbook.md` for the zero-downtime build and
swap procedure.

## Evaluation

`scripts/run_realcase_eval.py` checks the live API on organizer-track questions.
It verifies citation coverage, unsupported numbers, source-label leaks,
prompt-injection success, semantic support, evidence presence, and absence of
legacy fixture leakage.

## Repository Status

This repository is the working home for the 2026 hackathon submission. The older
pre-migration repository is frozen and is not used for deployment.

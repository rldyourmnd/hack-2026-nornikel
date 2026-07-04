# Full DATA_HACK ingest + atomic swap runbook

Zero-downtime build of the full corpus graph into a **separate** DuckDB file and
Qdrant collection while the live API keeps serving, then a seconds-long swap.

## Current stand LLM/embedding stack (2026-07-04)

The organizer **Yandex key is denied** (403 for both LLM and embeddings). Working stack:

- **LLM**: dataeyes (`DATAEYES_API_BASE/KEY` in server `.env`), `LLM_EXTRACTION_MODEL=openai/gpt-5.4-mini`, `LLM_ANSWER_MODEL=openai/gpt-5.5`.
- **Embeddings**: `EMBEDDING_BACKEND=openai` (dense via dataeyes `/embeddings`, `text-embedding-3-small`, 1536-dim, batched — offloads the 8-vCPU CPU), sparse BM25 local. `QDRANT_COLLECTION=evidence_oai`.

## Fast "Graph V0" profile (300-file sample, ~minutes)

The throughput floor is the LLM: 16-concurrent provider cap × ~15-30 s/call. To hit a
short build, use **source_packet** extraction (ONE LLM call per source, not 12) and a
bounded sample:

```bash
cd /srv/nornikel-kg-search
nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-full \
  -e DUCKDB_PATH=/app/data/catalog_next.duckdb \
  -e QDRANT_COLLECTION=evidence_next -e QDRANT_ENTITY_COLLECTION=evidence_next_entities \
  -e LLM_EXTRACTION_MODE=source_packet -e LLM_SOURCE_PACKET_CHARS=8000 \
  -e LLM_MAX_CONCURRENCY=16 -e DOCLING_PARSE_WORKERS=4 -e OMP_NUM_THREADS=1 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --sample 300 --workers 6 --max-mb 150 \
  > ingest_next.log 2>&1 < /dev/null &
```

- `LLM_EXTRACTION_MODE=source_packet` (the default): ~1 LLM call/source vs up to 12 → ~12× fewer extraction calls. `span_budget` opts back into the deep per-span path.
- `--sample 300`: reproducible random 300-file subset (seed 1234; re-run resumes via dedup).
- Trade-off: source_packet sees a representative packet (first ~8000 chars: head + early tables), so relations from deep sections are lighter than the span_budget graph.

## Run the full ingest (background, on the stand)

```bash
cd /srv/nornikel-kg-search
nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-full \
  -e DUCKDB_PATH=/app/data/catalog_full.duckdb \
  -e QDRANT_COLLECTION=evidence_full_oai -e QDRANT_ENTITY_COLLECTION=evidence_full_oai_entities \
  -e LLM_TOKEN_BUDGET=500000000 -e LLM_MAX_CONCURRENCY=8 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --workers 6 --max-mb 150 \
  > ingest_full.log 2>&1 < /dev/null &
```

- Writes a **separate** `catalog_full.duckdb` + `evidence_full_oai` collection — no lock/dim conflict with the live API (`catalog.duckdb` + `evidence_oai`).
- Idempotent (content-hash dedup) — safe to re-run/resume.
- Monitor: `tail -f ingest_full.log`; per-file lines are `[n/total] STATUS  Ns  K spans  name`.
- Bottleneck: Docling PDF parse is serialized (thread-lock) → ~hours for 1163 PDFs. Embedding is offloaded (API), so it no longer saturates CPU.

## Atomic swap (when the batch finishes)

```bash
cd /srv/nornikel-kg-search
docker compose -f docker-compose.server.yml stop api          # brief downtime starts
cp data/catalog.duckdb data/catalog.duckdb.bak-$(date +%s)     # backup current
mv data/catalog_full.duckdb data/catalog.duckdb                # swap the ledger
sed -i 's/^QDRANT_COLLECTION=.*/QDRANT_COLLECTION=evidence_full_oai/' .env
docker compose -f docker-compose.server.yml up -d api          # back up on the full graph
curl -s http://127.0.0.1:8080/api/stats/overview               # verify counts
```

Rollback: stop api, restore `catalog.duckdb.bak-*`, set `QDRANT_COLLECTION=evidence_oai`, start api.

## Speed levers (not yet applied)

- Remove the Docling serialization lock (`adapters/docling/parser.py` `_CONVERT_LOCK`) for parallel parsing — **only if** Docling proves thread-safe on this build (shared ML models can race). Test on a few files first.
- Raise `EMBEDDING_BATCH` (default 32; dataeyes 403s above ~32) if the provider limit is lifted.

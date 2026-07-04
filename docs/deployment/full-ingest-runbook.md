# DATA_HACK Ingest And Atomic Swap Runbook

This runbook builds a corpus graph into a separate DuckDB file and separate
Qdrant collections while the live API keeps serving. The live graph is switched
only after the batch completes and smoke checks pass.

## Runtime Profile

The production profile is configured entirely through server-side environment
variables:

- LLM: any verified OpenAI-compatible provider via `LLM_API_BASE`,
  `LLM_API_KEY`, `LLM_EXTRACTION_MODEL`, and `LLM_ANSWER_MODEL`.
- Dense embeddings: `EMBEDDING_BACKEND=openai` via `EMBEDDING_API_BASE`,
  `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL_ID`.
- Sparse retrieval: local BM25, kept as the lexical leg of hybrid search.
- PDF parsing: `PDF_PARSE_MODE=pypdfium` by default, which avoids local ML,
  GPU, and graphical-system dependencies.

Use a new Qdrant collection for each embedding dimension or backend change.

## Fast 300-File Build

Use this profile for a bounded jury graph build or for performance checks:

```bash
cd /srv/nornikel-kg-search
nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-next \
  -e DUCKDB_PATH=/app/data/catalog_next.duckdb \
  -e QDRANT_COLLECTION=evidence_next \
  -e QDRANT_ENTITY_COLLECTION=evidence_next_entities \
  -e LLM_EXTRACTION_MODE=source_packet \
  -e LLM_SOURCE_PACKET_CHARS=8000 \
  -e LLM_MAX_CONCURRENCY=16 \
  -e MAX_EXTRACTION_SPANS=400 \
  -e MAX_TABLE_ROWS_PER_SOURCE=400 \
  -e DOCLING_PARSE_WORKERS=4 \
  -e OMP_NUM_THREADS=1 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --sample 300 --workers 6 --max-mb 150 \
  > ingest_next.log 2>&1 < /dev/null &
```

Notes:

- `--sample 300` is reproducible with seed 1234.
- `source_packet` uses one extraction call per source and attributes extracted
  mentions back to the matching evidence spans.
- All evidence spans are still stored and indexed; `MAX_EXTRACTION_SPANS` and
  `MAX_TABLE_ROWS_PER_SOURCE` bound graph extraction work for very large files.

## Full Corpus Build

```bash
cd /srv/nornikel-kg-search
nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-full \
  -e DUCKDB_PATH=/app/data/catalog_full.duckdb \
  -e QDRANT_COLLECTION=evidence_full \
  -e QDRANT_ENTITY_COLLECTION=evidence_full_entities \
  -e LLM_EXTRACTION_MODE=source_packet \
  -e LLM_TOKEN_BUDGET=500000000 \
  -e LLM_MAX_CONCURRENCY=16 \
  -e MAX_EXTRACTION_SPANS=400 \
  -e MAX_TABLE_ROWS_PER_SOURCE=400 \
  -e DOCLING_PARSE_WORKERS=4 \
  -e OMP_NUM_THREADS=1 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --workers 6 --max-mb 150 \
  > ingest_full.log 2>&1 < /dev/null &
```

Monitor:

```bash
docker ps --filter name=ingest
tail -f ingest_full.log
curl -fsS http://127.0.0.1:6333/collections/evidence_full | jq '.result.points_count'
```

The batch is idempotent by content hash and can be resumed after a stop.

## Atomic Swap

Run the swap only after the batch exits successfully and the new collection
contains points.

```bash
cd /srv/nornikel-kg-search
docker compose -f docker-compose.server.yml stop api
cp data/catalog.duckdb data/catalog.duckdb.bak-$(date +%s)
mv data/catalog_full.duckdb data/catalog.duckdb
sed -i 's/^QDRANT_COLLECTION=.*/QDRANT_COLLECTION=evidence_full/' .env
sed -i 's/^QDRANT_ENTITY_COLLECTION=.*/QDRANT_ENTITY_COLLECTION=evidence_full_entities/' .env
docker compose -f docker-compose.server.yml up -d api
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/stats/overview
```

Rollback:

```bash
cd /srv/nornikel-kg-search
docker compose -f docker-compose.server.yml stop api
mv data/catalog.duckdb.bak-<timestamp> data/catalog.duckdb
sed -i 's/^QDRANT_COLLECTION=.*/QDRANT_COLLECTION=evidence_oai/' .env
sed -i 's/^QDRANT_ENTITY_COLLECTION=.*/QDRANT_ENTITY_COLLECTION=evidence_oai_entities/' .env
docker compose -f docker-compose.server.yml up -d api
```

## Operational Checks

- `tail -f ingest_*.log`: per-file status, duration, span count, and provenance.
- `docker stats`: CPU/RAM during parsing and embedding.
- `/api/stats/overview`: source/span/fact/relation counts after swap.
- `API_BASE=<stand>/api uv run python scripts/run_realcase_eval.py`: live
  evidence and honesty gate.

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
- DataEyes `openai/gpt-5.4-mini` accepts `LLM_REASONING_EFFORT=low` through
  LiteLLM, but GPT-5-family chat completions require `temperature=1`; the
  gateway handles that automatically. Do not set output token caps for
  structured JSON extraction because truncated JSON fails validation.

Use a new Qdrant collection for each embedding dimension or backend change.

## Verified Throughput Facts

The current no-GPU production profile is DataEyes/OpenAI-compatible
`openai/gpt-5.4-mini` with `LLM_REASONING_EFFORT=low` and
`EMBEDDING_MODEL_ID=text-embedding-3-small`.

Measured on the stand against the same seeded 40-file DATA_HACK sample
(`--sample 40`, seed 1234, `--max-mb 25`):

| Profile | Result |
| --- | --- |
| Previous single-process DataEyes/MiniMax profile | 40/40 in 1439s, 0 failed |
| Single-process `gpt-5.4-mini` + `text-embedding-3-small` | 40/40 in 790s, 0 failed, 4 provider retries |
| Four-shard `gpt-5.4-mini` + `text-embedding-3-small` | 40/40 in 500s max shard wall time, 0 failed, 1 provider retry |
| Eight-shard `gpt-5.4-mini` + `text-embedding-3-small` stress profile | 300/300 in 1341s max shard wall time, 297 completed, 3 quarantined, 0 failed, 0 provider retries |

The four-shard benchmark produced a merged ledger with 40 sources, 16,102
evidence spans, 1,067 entities, 23,672 numeric facts, and a shared Qdrant
collection with 16,102 points.

The eight-shard 300-file benchmark used `--sample 300`, `--workers 24` per
shard, `LLM_MAX_CONCURRENCY=256`, `LLM_RPS=256`, `EMBEDDING_BATCH=512`, and
`EMBEDDING_RPS=64`. It produced a merged ledger with 299 unique sources
(one cross-shard content duplicate collapsed during merge), 92,118 evidence
spans, 5,500 entities, 8,322 relations, 155,143 numeric facts, and a shared
Qdrant collection with 92,118 points.

Operational conclusion: DuckDB read replicas do not speed ingest. The useful
pattern is write sharding: independent `DUCKDB_PATH` files per shard, then a
deterministic merge before the atomic swap.

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
  -e LLM_REASONING_EFFORT=low \
  -e LLM_MAX_CONCURRENCY=128 \
  -e LLM_RPS=128 \
  -e EMBEDDING_MODEL_ID=text-embedding-3-small \
  -e EMBEDDING_BATCH=256 \
  -e EMBEDDING_RPS=32 \
  -e MAX_EXTRACTION_SPANS=400 \
  -e MAX_TABLE_ROWS_PER_SOURCE=400 \
  -e DOCLING_PARSE_WORKERS=4 \
  -e OMP_NUM_THREADS=1 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --sample 300 --workers 24 --max-mb 150 \
  > ingest_next.log 2>&1 < /dev/null &
```

Notes:

- `--sample 300` is reproducible with seed 1234.
- `source_packet` uses one extraction call per source and attributes extracted
  mentions back to the matching evidence spans.
- All evidence spans are still stored and indexed; `MAX_EXTRACTION_SPANS` and
  `MAX_TABLE_ROWS_PER_SOURCE` bound graph extraction work for very large files.

## Sharded 300-File Build

For maximum CPU/API utilization on a no-GPU stand, prefer the sharded build.
Each shard writes to its own DuckDB file, avoiding the per-process single-writer
ledger bottleneck, while all shards can write vectors into the same fresh Qdrant
collections. Merge the shard ledgers before the final swap.

```bash
cd /srv/nornikel-kg-search
SHARDS=8
for i in $(seq 0 $((SHARDS - 1))); do
  nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-next-$i \
    -e DUCKDB_PATH=/app/data/catalog_next_shard_${i}.duckdb \
    -e QDRANT_COLLECTION=evidence_next \
    -e QDRANT_ENTITY_COLLECTION=evidence_next_entities \
    -e LLM_EXTRACTION_MODE=source_packet \
    -e LLM_REASONING_EFFORT=low \
    -e LLM_TOKEN_BUDGET=500000000 \
    -e LLM_MAX_CONCURRENCY=256 \
    -e LLM_RPS=256 \
    -e EMBEDDING_MODEL_ID=text-embedding-3-small \
    -e EMBEDDING_BATCH=512 \
    -e EMBEDDING_RPS=64 \
    -e MAX_EXTRACTION_SPANS=400 \
    -e MAX_TABLE_ROWS_PER_SOURCE=400 \
    -e DOCLING_PARSE_WORKERS=1 \
    -e OMP_NUM_THREADS=1 \
    api python scripts/ingest_corpus.py --dir DATA_HACK --sample 300 --workers 24 --max-mb 150 \
      --shard-count $SHARDS --shard-index $i \
    > ingest_next_shard_${i}.log 2>&1 < /dev/null &
done
```

After all shard containers exit successfully:

```bash
python scripts/merge_duckdb_shards.py \
  --output data/catalog_next.duckdb \
  data/catalog_next_shard_*.duckdb
```

## Full Corpus Build

Single-process fallback for the full selected corpus:

```bash
cd /srv/nornikel-kg-search
nohup docker compose -f docker-compose.server.yml run --rm --no-deps -T --name ingest-full \
  -e DUCKDB_PATH=/app/data/catalog_full.duckdb \
  -e QDRANT_COLLECTION=evidence_full \
  -e QDRANT_ENTITY_COLLECTION=evidence_full_entities \
  -e LLM_EXTRACTION_MODE=source_packet \
  -e LLM_TOKEN_BUDGET=500000000 \
  -e LLM_REASONING_EFFORT=low \
  -e LLM_MAX_CONCURRENCY=128 \
  -e LLM_RPS=128 \
  -e EMBEDDING_MODEL_ID=text-embedding-3-small \
  -e EMBEDDING_BATCH=256 \
  -e EMBEDDING_RPS=32 \
  -e MAX_EXTRACTION_SPANS=400 \
  -e MAX_TABLE_ROWS_PER_SOURCE=400 \
  -e DOCLING_PARSE_WORKERS=4 \
  -e OMP_NUM_THREADS=1 \
  api python scripts/ingest_corpus.py --dir DATA_HACK --workers 24 --max-mb 150 \
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

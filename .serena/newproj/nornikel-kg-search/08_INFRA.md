# Infrastructure

## P0 Server Deployment

Use a server-first deployment for the working demo on `fa.nddev.asia` via `ssh server-nddev`:

- `frontend`: React/Vite static app;
- `api`: FastAPI backend;
- `duckdb`: local database file for source registry, facts, evaluations, and gap analytics;
- `qdrant`: Docker container with persisted volume;
- `artifacts/`: local generated artifact memory bank.

P1/productization adds:

- `postgres`: app state and audit;
- `neo4j`: persistent graph database;
- `worker`: ingestion and extraction queue workers;
- `minio` or S3-compatible object storage.

## Environment Configuration

Required configuration groups:

- metadata store URL/path;
- graph adapter setting;
- graph database URL and credentials when using Neo4j;
- vector database URL;
- object storage path/bucket;
- LiteLLM/OpenAI-compatible LLM provider configuration;
- LiteLLM/OpenAI-compatible embedding provider configuration;
- auth mode, default `disabled`;
- security label defaults;
- logging level.

Secrets must live outside the repository.

P0 `.env.example` should include placeholders only (amended 2026-07-02 — open-weight
matrix from `.serena/plans/06_DEPLOYMENT_AND_OBSERVABILITY.md`; OpenAI defaults
withdrawn per hackathon rules):

- `LLM_ENABLED=false` (CI/tests) / `true` (server);
- `DATAEYES_API_BASE=https://api.dataeyes.ai/v1`, `DATAEYES_API_KEY`;
- `LLM_EXTRACTION_MODEL`, `LLM_ANSWER_MODEL` (open-weight IDs chosen in W0);
- `EMBEDDING_BACKEND=local`, `EMBEDDING_MODEL_ID=deepvk/USER-bge-m3`,
  `SPARSE_MODEL_ID=Qdrant/bm25`, `HF_HOME=/app/data/hf-cache`;
- `OLLAMA_BASE_URL=http://ollama:11434` (fallback profile);
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`;
- `QDRANT_URL=http://qdrant:6333`;
- `DUCKDB_PATH=data/catalog.duckdb`;
- `ARTIFACT_ROOT=data/artifacts`;
- `APP_BASE_URL=https://nornikel.nddev.asia`.

## Jobs

Ingestion stages:

1. source_register;
2. parse;
3. chunk;
4. dictionary_import;
5. extract;
6. resolve_entities;
7. write_graph_path;
8. index_vectors;
9. quality_report.

Each stage must be retryable and idempotent. In MVP-lite, stages can run synchronously but must still persist job state in DuckDB so failed parsing or extraction is visible.

## Observability

Log structured events:

- request ID;
- user ID;
- source ID;
- job ID;
- extraction run ID;
- QA run ID;
- retrieval plan;
- graph query ID;
- vector query ID;
- latency;
- error class.

For MVP, structured JSON logs are enough. Later, add OpenTelemetry traces and metrics dashboards.

## Backups

MVP:

- snapshot DuckDB file;
- snapshot Qdrant collection;
- archive artifact memory bank;
- keep original source files immutable.

P1:

- export Neo4j dump after successful demo ingestion;
- snapshot PostgreSQL volume;

Production direction:

- scheduled database backups;
- object storage versioning;
- migration plan for schema changes;
- disaster recovery runbook.

## Scaling Path

- Move workers to queue-backed service.
- Promote DuckDB metadata store to PostgreSQL when concurrent writes, multi-user review, or audit requirements demand it.
- Promote NetworkX graph adapter to Neo4j when graph size, Cypher querying, or persistent graph exploration demand it.
- Split parser/extractor/indexer workloads.
- Add caching for entity pages and repeated QA queries.
- Add graph precomputed neighborhoods for high-traffic materials.
- Add offline graph analytics for central materials, missing links, and team expertise.

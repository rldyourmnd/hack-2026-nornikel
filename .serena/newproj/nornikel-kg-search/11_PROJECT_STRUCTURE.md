# Proposed Project Structure

Owner approval for scaffold/code implementation was given. Use this minimal useful structure.

```text
.
├── pyproject.toml
├── uv.lock
├── Makefile
├── docker-compose.yml
├── .env.example
├── apps
│   └── web
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── index.html
│       └── src
│           ├── app
│           ├── pages
│           ├── features
│           ├── entities
│           ├── shared
│           └── widgets
├── services
│   └── api
│       ├── main.py
│       ├── routes
│       │   ├── ingest.py
│       │   ├── query.py
│       │   ├── evidence.py
│       │   ├── graph.py
│       │   └── eval.py
│       └── schemas.py
├── src
│   └── nornikel_kg
│       ├── domain
│       │   ├── ids.py
│       │   ├── models.py
│       │   ├── evidence.py
│       │   ├── materials.py
│       │   ├── regimes.py
│       │   ├── measurements.py
│       │   ├── effects.py
│       │   ├── conflicts.py
│       │   ├── gaps.py
│       │   └── answer_claims.py
│       ├── ports
│       │   ├── artifact_store.py
│       │   ├── metadata_store.py
│       │   ├── parser.py
│       │   ├── vector_index.py
│       │   ├── graph_store.py
│       │   ├── embedding_model.py
│       │   ├── sparse_encoder.py
│       │   ├── llm_client.py
│       │   └── acl_policy.py
│       ├── adapters
│       │   ├── artifact_fs
│       │   ├── duckdb
│       │   │   └── migrations
│       │   │       └── 001_init.sql
│       │   ├── docling
│       │   ├── qdrant
│       │   ├── networkx
│       │   └── llm
│       ├── pipelines
│       │   ├── ingest.py
│       │   ├── build_evidence.py
│       │   ├── extract.py
│       │   ├── normalize.py
│       │   ├── index.py
│       │   ├── answer.py
│       │   ├── evaluate.py
│       │   └── security_checks.py
│       ├── services
│       │   ├── ingestion_service.py
│       │   ├── extraction_service.py
│       │   ├── indexing_service.py
│       │   ├── qa_service.py
│       │   ├── graph_service.py
│       │   └── evaluation_service.py
│       └── resources
│           ├── dictionaries
│           │   ├── materials.yml
│           │   ├── properties.yml
│           │   ├── regimes.yml
│           │   ├── units.yml
│           │   ├── equipment.yml
│           │   └── teams.yml
│           ├── prompts
│           │   ├── extract_fact.json.md
│           │   ├── answer_from_evidence.md
│           │   └── verify_claims.md
│           └── fixtures
│               ├── gold_questions.yml
│               ├── adversarial_questions.yml
│               └── expected_spans.yml
├── data
│   ├── .gitkeep
│   ├── catalog.duckdb
│   ├── artifacts
│   └── qdrant_storage
├── eval
│   ├── gold_questions.yml
│   ├── adversarial_questions.yml
│   └── expected_spans.yml
├── sample_docs
│   ├── synthetic
│   └── README.md
├── tests
│   ├── unit
│   └── integration
├── docs
│   ├── architecture
│   ├── demo
│   └── deployment
├── .github
│   └── workflows
│       └── ci.yml
└── .serena
    └── newproj
```

## Module Boundaries

- `domain`: stable scientific schemas and invariants.
- `ports`: dependency boundaries for stores, parsers, models, auth, graph, and retrieval.
- `adapters`: concrete MVP-lite implementations.
- `pipelines`: executable ingestion, evidence, extraction, indexing, QA, evaluation, and security flows.
- `services`: application service orchestration used by API and future workers.
- `apps/web`: React/Vite judge-facing workbench and production UI.
- `services/api`: stable API contracts only; keep business logic in `src/nornikel_kg/services`.

## Adapter Rule

Every external dependency must sit behind a port:

- `ArtifactStore`: local filesystem first, S3-compatible later.
- `MetadataStore`: DuckDB first, PostgreSQL later.
- `GraphStore`: DuckDB edge tables plus NetworkX first, Neo4j later.
- `VectorStore`: Qdrant first, OpenSearch/pgvector later only if required.
- `DocumentParser`: Docling first, parser bakeoff alternatives later.
- `ModelProvider`: configurable hosted or local model.
- `EmbeddingProvider`: dense and sparse embedding providers.
- `AuthProvider`: disabled/demo-open first, SSO/RBAC later.

## Required Make Targets

- `make install`: install local development dependencies.
- `make test`: run unit and integration tests.
- `make ingest-fixtures`: ingest curated sample documents.
- `make eval`: run gold and adversarial evaluation.
- `make web`: run the React/Vite dev server.
- `make api`: run the FastAPI dev server.
- `make demo`: start API, web, Qdrant, and required local services.
- `make deploy`: deploy the current approved branch to `fa.nddev.asia`.

## Data Directory Rule

Synthetic sample data and schema fixtures should be committed. Real internal corpora may be committed only when the owner explicitly provides/approves them for this private repository; generated runtime artifacts, local databases, Qdrant storage, caches, and secrets still must not be committed.

## Artifact Directory Rule

Runtime artifact memory bank files are generated from source corpora and must not be committed unless they are synthetic fixtures. The intended shape is:

```text
data/artifacts/
└── sources/
    └── src_...
        ├── raw/
        ├── manifest.json
        ├── docling/document.md
        ├── docling/document.json
        ├── pages/
        ├── tables/
        ├── figures/
        ├── chunks/
        └── extraction/
```

## Migration Direction

Start with a modular Python backend and React frontend. Promote adapters only when the P0 evidence loop works and the scale trigger is real:

- DuckDB to PostgreSQL for multi-user review/audit.
- NetworkX to Neo4j for durable graph queries and Cypher.
- In-process jobs to worker queues for long ingestion.
- Local artifacts to object storage for shared deployment.

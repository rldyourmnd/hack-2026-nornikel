# Architecture Decision Records

## ADR-001: Use Hybrid KG Plus Semantic Search

Status: Proposed

Decision: Build a hybrid system combining a canonical knowledge graph, vector/sparse retrieval, and grounded answer assembly.

Rationale:

- Target questions require both relationship traversal and text evidence retrieval.
- Graph-only systems struggle with incomplete extraction and narrative documents.
- Vector-only systems cannot reliably explain multi-hop material to regime to property to conclusion chains.

Consequences:

- More moving parts than a simple RAG app.
- Stronger demo value: answer, evidence, graph, conflicts, and gaps.
- Requires artifact memory bank discipline so generated Markdown remains traceable to structured source spans.

## ADR-002: Use NetworkX First, Neo4j Later

Status: Proposed

Decision: Use DuckDB graph node/edge tables plus NetworkX `MultiDiGraph` for P0 graph paths. Promote to Neo4j only after the evidence loop works and persistent graph queries justify the operational cost.

Rationale:

- P0 needs explainable answer paths, not a full graph database.
- NetworkX can materialize answer neighborhoods from DuckDB facts without extra infrastructure.
- Keeping the `GraphStore` port makes Neo4j adoption straightforward when graph size, Cypher queries, multi-user exploration, or graph analytics become core.

Consequences:

- Neo4j Community licensing must be reviewed before productization because it is GPLv3.
- Neo4j remains a P1 adapter, not a P0 blocker.

Alternatives:

- PostgreSQL plus recursive SQL: lower operational cost, weaker graph ergonomics.
- RDF triple store: strong ontology semantics, slower hackathon iteration.
- Neo4j from day one: stronger graph tooling but too much infrastructure risk for the hackathon.

## ADR-003: Use Qdrant For Hybrid Retrieval

Status: Proposed

Decision: Use Qdrant for dense plus sparse vectors and fusion-based hybrid retrieval.

Rationale:

- Hybrid retrieval is important for exact alloy names and semantic phrasing.
- Qdrant supports dense and sparse vectors, payload filters, and reciprocal-rank-fusion style hybrid queries.
- It keeps retrieval independent from the graph database.

Alternatives:

- OpenSearch: strong enterprise search option if the organization already operates it.
- pgvector: simpler stack, but less specialized for advanced hybrid retrieval and payload-heavy vector search.
- Neo4j vector only: fewer services, but mixes graph and retrieval concerns too early.

## ADR-004: Use DuckDB As P0 Evidence Ledger

Status: Proposed

Decision: Use DuckDB as the P0 system of record for source registry, artifacts, evidence spans, facts, graph node/edge tables, answer claims, evaluation, security checks, and gap analytics.

Rationale:

- DuckDB is embedded, fast to ship, and well suited to local analytical workloads.
- The first product needs a scientific evidence ledger more than a multi-user OLTP service.
- DuckDB keeps demo setup simple while preserving a clear path to PostgreSQL through `MetadataStore`.

Consequences:

- Qdrant is retrieval-only and cannot be authoritative for facts or provenance.
- PostgreSQL remains the P1 adapter for multi-user review, audit, and concurrent writes.

## ADR-005: Use FastAPI For Backend API

Status: Proposed

Decision: Use FastAPI for typed API services, OpenAPI docs, async endpoints, dependency injection, and background job integration.

Rationale:

- Python ecosystem is strongest for document parsing, embeddings, LLM extraction, scientific tooling, and rapid prototype work.
- FastAPI keeps contracts explicit and demoable.

## ADR-006: Keep LLM Provider Swappable

Status: Proposed

Decision: LLM extraction, answer generation, and embeddings must be behind provider interfaces. Use LiteLLM/OpenAI-compatible external APIs for P0, configured only through environment variables and server secrets.

Rationale:

- The owner approved external API use for this hackathon.
- LiteLLM keeps model/provider changes out of domain code.
- Local/on-prem models can still be added later through the same ports.
- Evaluation and provenance should not depend on one vendor.

Consequences:

- `gpt-5.5-mini` is treated as an owner-provided LiteLLM alias until the exact provider model ID is verified in the deployment account.
- Official OpenAI docs currently confirm `gpt-5.5` availability and OpenAI embedding models such as `text-embedding-3-large`; deployment must keep model names configurable.

## ADR-007: Provenance Is Mandatory

Status: Proposed

Decision: Every extracted fact and relationship must carry source span, extraction run, extractor type, confidence, validation status, and reviewer metadata where applicable.

Rationale:

- Scientific users need evidence and reproducibility.
- Provenance enables conflict detection, trust scoring, and audit.

## ADR-008: Use React/Vite For P0 Workbench

Status: Proposed

Decision: Use React 19, Vite 8, TypeScript, and a graph/table-oriented UI stack for the P0 workbench instead of Streamlit.

Rationale:

- The owner prioritized a polished, visually strong product on the server over fastest local prototyping.
- Vite 8 supports the current React template and requires Node 20.19+ or 22.12+; use Node 24 LTS for the server baseline.
- React gives better graph exploration, evidence cards, dense tables, and security/evaluation dashboards than a Python-only workbench.

Consequences:

- FastAPI is required from the first scaffold.
- Browser validation becomes mandatory for UI changes.
- Streamlit is no longer part of P0.

## ADR-009: Use Python 3.12 And Server-First Docker Compose

Status: Proposed

Decision: Use Python 3.12 for backend/scientific tooling and Docker Compose deployment to `fa.nddev.asia` via `ssh server-nddev`.

Rationale:

- Python 3.12 is current enough while reducing compatibility risk for Docling, OCR, scientific parsing, and binary dependencies.
- The owner confirmed the project will run on a server, not as a local-only demo.
- Docker Compose gives repeatable API/frontend/Qdrant/runtime volume orchestration without prematurely adding Kubernetes or queues.

Consequences:

- CI must validate both backend and frontend.
- Deployment configuration must use `.env.example` placeholders and server-side secrets, not committed keys.

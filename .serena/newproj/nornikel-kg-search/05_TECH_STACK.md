# Tech Stack

## Recommended P0 Stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Frontend | React 19, Vite 8, TypeScript | Polished graph/evidence workbench, production-like UX, and simple static deployment |
| UI/Graph | React Flow or Cytoscape.js, TanStack Table, shadcn/ui-style primitives | Rich answer-path visualization, dense evidence tables, and maintainable components |
| Backend API | FastAPI, Pydantic | Typed contracts, OpenAPI, async endpoints, and Python-native ingestion/QA services |
| Runtime | Python 3.12, Node 24 LTS | Stable compatibility for Docling/OCR/scientific Python while meeting current Vite Node requirements |
| App/Analytics DB | DuckDB | Embedded persistence for source registry, artifacts, extracted facts, and gap analytics |
| Graph Adapter | NetworkX first | In-memory typed graph paths and node-link export without Neo4j setup cost |
| Vector Search | Qdrant local/Docker | Dense plus sparse hybrid retrieval, payload filters, and production-compatible API |
| Document Parsing | Docling first, GROBID for scholarly PDF fallback | Markdown/JSON artifacts, OCR, layout, tables, references |
| Lightweight Conversion | MarkItDown optional | Quick Markdown conversion for simple Office/PDF inputs |
| Parse QA Alternatives | Unstructured, Marker, MinerU | Compare on hard PDFs, scanned images, tables, formulas |
| Workers | Synchronous job runner first | Simpler MVP; promote to queue when ingestion becomes long-running |
| Object Storage | Local artifact directory | Original files, Markdown, structured JSON, tables, images, manifests |
| Auth MVP | No user auth; source security labels only | Owner confirmed open demo access; keep security/provenance labels for future RBAC |
| LLM Gateway | LiteLLM Python SDK first | Provider/model can be changed through env without rewriting domain code |
| Embeddings | LiteLLM/OpenAI-compatible embeddings first, local fallback later | External APIs are allowed; keep provider behind `EmbeddingModelPort` |
| Deployment | Docker Compose on `fa.nddev.asia` | Server-first demo with API, frontend, Qdrant, and persisted local artifacts |
| Observability | Structured logs, OpenTelemetry-ready IDs | Trace ingestion and answer provenance |

## P1/Productization Adapters

| Port | MVP-Lite Adapter | P1 Adapter |
| --- | --- | --- |
| MetadataStore | DuckDB | PostgreSQL |
| GraphStore | NetworkX over typed facts | Neo4j |
| WorkbenchUI | React + Vite | Same stack, richer design system and production routing |
| JobRunner | In-process runner | Celery/RQ/Arq worker queue |
| ArtifactStore | Local filesystem | S3-compatible object storage |
| AuthProvider | Disabled/demo-open with labels | Corporate SSO/RBAC |

## Retrieval Tooling

Use Qdrant collections for:

- Markdown chunks;
- structured table rows;
- document chunks;
- extracted claims;
- entity summaries;
- experiment summaries.

Each record should include:

- dense embedding;
- sparse/BM25-like vector where supported;
- payload filters for material, property, regime, equipment, lab, source, artifact type, page number, table ID, image/figure ID, date, security label, validation status.

## Graph Tooling

Use the same labels in both NetworkX and Neo4j adapters:

- Material;
- Alloy;
- MaterialComposition;
- Experiment;
- Sample;
- BatchOrHeat;
- ProcessingRegime;
- ProcessStep;
- ProcessParameter;
- Property;
- PropertyMeasurement;
- EffectClaim;
- Equipment;
- Installation;
- Team;
- Person;
- Lab;
- Document;
- EvidenceSpan;
- Table;
- TableRow;
- TableCell;
- Figure;
- Claim;
- Conclusion;
- Decision;
- ConflictGroup;
- DataGap.

Use relationship types:

- MENTIONS;
- USES_SAMPLE;
- MADE_OF;
- HAS_COMPOSITION;
- APPLIES_REGIME;
- HAS_STEP;
- HAS_PARAMETER;
- HAS_MEASUREMENT;
- OF_PROPERTY;
- PRODUCED_EFFECT;
- COMPARES_BASELINE;
- COMPARES_TREATED;
- PERFORMED_BY;
- USED_EQUIPMENT;
- AUTHORED_BY;
- SUPPORTS;
- CONTRADICTS;
- DERIVED_FROM;
- SUPPORTED_BY;
- FROM_DOCUMENT;
- REVIEWED_BY;
- HAS_GAP;
- ADDRESSES_GAP;
- REQUIRES_FOLLOWUP.

## LLM And Embeddings

Keep providers configurable through `.env` and never commit real keys:

- extraction model;
- answer model;
- embedding model;
- reranker.

P0 defaults (amended 2026-07-02 per hackathon rules — open-weight models only, see
`.serena/plans/01_MVP_SCOPE_AND_DECISIONS.md`; the previous `openai/gpt-5.5-mini` /
`openai/text-embedding-3-large` defaults are withdrawn):

- `LLM_ENABLED=false` in CI/tests (deterministic FakeLLM path), `true` on the server;
- `DATAEYES_API_BASE` + `DATAEYES_API_KEY` — OpenAI-compatible router restricted to
  open-weight catalog models (DeepSeek/Qwen/GLM/Kimi class, weights verified on HF);
- `LLM_EXTRACTION_MODEL` / `LLM_ANSWER_MODEL` — LiteLLM strings chosen in W0 discovery;
- `EMBEDDING_BACKEND=local` with `EMBEDDING_MODEL_ID=deepvk/USER-bge-m3` (dense) and
  `SPARSE_MODEL_ID=Qdrant/bm25` (fastembed);
- `OLLAMA_BASE_URL` — optional self-hosted fallback (`ollama_chat/qwen3:4b|8b`);
- keys supplied only through server secrets; full matrix in
  `.serena/plans/06_DEPLOYMENT_AND_OBSERVABILITY.md`.

Hard requirements:

- structured extraction output;
- deterministic schema validation;
- source-grounded answer generation;
- no direct graph writes from model output;
- no uncited final answers.

## Document Artifact Decision

Use Docling as the default parser because it supports document conversion to Markdown and structured document formats, OCR, layout-aware parsing, table recovery, image export, and RAG chunking. Use GROBID for scholarly PDFs when references, citation contexts, and TEI/XML structure matter.

Do not use a flat folder of Markdown files as the whole memory system. Use Markdown as the readable projection of a richer artifact bundle:

- Markdown for fast inspection and text retrieval.
- JSON/DoclingDocument or equivalent for structure and source spans.
- Extracted assets for tables, figures, page images, and OCR review.
- Manifest files for checksums, parser versions, security labels, and reproducibility.

## Alternatives To Keep Open

- OpenSearch instead of Qdrant if enterprise search integration is required.
- PostgreSQL plus pgvector for a smaller MVP if operational simplicity matters more than hybrid retrieval quality.
- Neo4j for P1 when persistent graph queries, Cypher, multi-user graph exploration, or graph analytics become necessary.
- RDF/OWL store for future ontology-heavy integration, not for first hackathon implementation.

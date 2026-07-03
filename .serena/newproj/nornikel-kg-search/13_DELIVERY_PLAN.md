# Delivery Plan

## Hackathon Plan

## Critical Path

Do not start with a broad knowledge graph. Start with one vertical slice:

```text
sample corpus
-> artifact memory bank
-> EvidenceSpan IDs
-> material/regime/property/measurement extraction
-> canonical graph path
-> hybrid retrieval
-> answer table with citations
-> gap result
```

This path must work before graph visualization, domain NLP, or community-level GraphRAG summaries.

## P0 Delivery Principle

Use the lightest adapter that proves the product contract:

- DuckDB before PostgreSQL.
- NetworkX before Neo4j.
- React/Vite now, because the owner wants a polished server-facing product UI.
- In-process job runner before worker queues.
- Local artifact directory before object storage.

The code must still be written through ports so each adapter can be replaced without changing domain logic.

## Pre-Code Must-Fix Checklist

- Freeze ID policy for `source_id`, `artifact_id`, `span_id`, `extraction_run_id`, `fact_id`, and `claim_id`.
- Make DuckDB the P0 system of record.
- Treat table rows and cells as first-class evidence.
- Define `EffectClaim`, `ConflictGroup`, `DataGap`, and `answer_claims`.
- Create gold questions, including one ideal demo scenario plus success, conflict, gap, source-label, and prompt-injection cases.
- Use LiteLLM/OpenAI-compatible external APIs for LLM and embeddings; configure with secrets only.
- Enforce source-label filtering before LLM context construction.
- Make answer output a claim ledger, not a prose blob.

### Phase 0: Owner Decisions

Owner decisions now confirmed:

- scaffold/code implementation is approved;
- merge planning work to `main` and continue in logical branches;
- use external APIs via LiteLLM and prepared secret placeholders;
- use Docker Compose;
- use `uv`;
- use React/Vite frontend and FastAPI backend;
- deploy to `fa.nddev.asia` via `ssh server-nddev`;
- create synthetic test/demo documents for PDF, DOCX, XLSX, CSV, PPTX, and images;
- no user auth/RBAC in P0;
- responses are Russian-first.

### Phase 1: Foundation

Deliver:

- repository scaffold;
- Python 3.12 workspace for API, domain packages, ingestion, and tests;
- React 19/Vite 8/TypeScript workspace for the frontend;
- Docker Compose MVP profile for API, frontend, Qdrant, and volumes;
- GitHub Actions CI for backend tests, frontend type/lint/build checks, docs hygiene, and secret scan;
- source registry schema;
- artifact memory bank layout and manifest schema;
- minimal domain schemas;
- seed dictionaries for materials, equipment, teams, and properties.
- one synthetic or approved sample corpus that can be committed or safely mounted on the server.
- gold/adversarial question fixtures and expected evidence spans.

### Phase 2: Ingestion

Deliver:

- PDF/DOCX/CSV ingest;
- Docling-based Markdown plus structured JSON conversion;
- optional GROBID path for scholarly PDFs;
- extracted table/image artifacts;
- chunking with stable source spans;
- structured extraction into candidate facts;
- entity resolution against dictionaries;
- graph path materialization through NetworkX adapter;
- vector index in Qdrant.
- quarantine queue for parse failures and low-confidence spans.

### Phase 3: Search And Graph

Deliver:

- hybrid search endpoint;
- entity lookup;
- graph path/neighborhood endpoint backed by GraphStore port;
- experiment/property comparison query;
- gap detection prototype.
- answer claim verifier with unsupported-claim blocking.

### Phase 4: QA And UI

Deliver:

- React research workbench UI;
- QA answer with citations;
- evidence table;
- graph path view;
- gap board;
- timeline if the P0 answer path is already stable;
- review queue basics if extraction confidence issues are blocking demo trust.

### Phase 5: Evaluation And Demo

Deliver:

- seed demo corpus;
- one ideal demo scenario plus 10-20 regression/evaluation questions;
- retrieval/evidence report;
- demo script;
- risk list and production roadmap.

## Demo Script

1. Upload or import the corpus.
2. Show ingestion status and extracted entity counts.
3. Ask: "What has already been done for alloy X under regime Y, and what effect was observed on property Z?"
4. Open evidence table and source snippets.
5. Show graph path from alloy to experiment to regime to measurement to conclusion.
6. Show related equipment and team.
7. Show timeline of decisions.
8. Show missing or conflicting data.
9. Approve a candidate fact and show graph/search update.

## Production Roadmap

After hackathon:

- integrate corporate SSO and authorization model;
- connect live source systems;
- expand ontology and validation rules;
- build human review workflows;
- add offline graph analytics;
- add scheduled ingestion;
- add full audit and compliance controls;
- scale evaluation with curated gold datasets.

## Explicit Approval Gate

Closed on 2026-06-28 by owner instruction. Implementation may proceed in logical branches from `main`.

# MVP Blueprint

## Goal

Build the smallest working product that proves the hackathon value:

> A researcher asks what was done for a material under a process regime and what happened to a property. The system returns an experiment table, exact evidence spans, graph path, conflicts or gaps, and a grounded answer.

## Non-Negotiable Product Contract

The MVP is working only if it can complete this loop:

```text
Upload/import source files
-> create artifact memory bank
-> generate EvidenceSpan IDs
-> extract material/regime/property/measurement facts
-> materialize graph path
-> index searchable evidence
-> answer a question with cited experiment table
-> show missing data/gap
```

## P0 Architecture

```text
React/Vite Workbench
        |
FastAPI API
        |
Application Services
        |
Domain Ports
        |
+------------------+-----------------+------------------+----------------+
| ArtifactStore    | MetadataStore   | GraphStore       | VectorStore    |
| local filesystem | DuckDB          | NetworkX         | Qdrant         |
+------------------+-----------------+------------------+----------------+
        |
Docling artifacts + extraction pipeline + QA/evaluation
```

## System Of Record

DuckDB is the P0 system of record.

- The artifact memory bank stores raw files and parser outputs.
- DuckDB stores source registry, ingestion runs, artifact metadata, evidence spans, dictionaries, normalized facts, graph node/edge tables, answer claims, evaluation results, and source security-label decisions.
- Qdrant retrieves candidate evidence units only; it is never authoritative for facts or provenance.
- NetworkX materializes graph paths from DuckDB node/edge tables on demand; it is not persistent graph state.
- React/Vite is the workbench; it must call FastAPI and never bypass application services.

If DuckDB and Qdrant disagree, DuckDB wins.

## Why This Is The Right MVP Shape

- It is buildable as a real product slice: Python backend, React frontend, Qdrant, and Docker Compose.
- It is modular: domain code depends on ports, not vendor clients.
- It is scalable later: DuckDB to PostgreSQL, NetworkX to Neo4j, in-process jobs to queues, local artifacts to object storage.
- It is demo-friendly: React can provide a polished graph/evidence experience on `fa.nddev.asia`.
- It keeps the core trust feature: every claim maps to an `EvidenceSpan`.

## P0 Modules

### `domain`

Owns schemas and invariants:

- Material;
- MaterialComposition;
- Sample;
- Experiment;
- ProcessingRegime;
- ProcessStep;
- Property;
- PropertyMeasurement;
- EffectClaim;
- EvidenceSpan;
- Document;
- ConflictGroup;
- Gap.

Rules:

- measurements require units;
- table rows and table cells are first-class evidence;
- effect claims require baseline/treated measurements or `qualitative_only`;
- final-answer claims require `EvidenceSpan`;
- graph path uses the canonical relationship names;
- model output is candidate data until validated.

### `ingestion`

Owns source processing:

- source registration;
- Docling conversion;
- artifact manifest;
- table/image extraction;
- chunking;
- parser quality report;
- quarantine.

### `extraction`

Owns candidate facts:

- dictionary matching;
- regex/rule extraction for units, temperatures, durations, compositions, and values;
- structured table extraction;
- LLM JSON extraction on small chunks;
- schema validation;
- confidence scoring.

### `retrieval`

Owns evidence search:

- dense embeddings;
- sparse embeddings;
- Qdrant payload filters;
- hybrid retrieval;
- reranking by exact slot match and evidence quality.

### `graph`

Owns typed paths:

- store graph nodes/edges in DuckDB;
- build NetworkX `MultiDiGraph` from DuckDB facts on demand;
- return path and neighborhood JSON;
- keep Neo4j adapter contract ready.

### `qa`

Owns answer assembly:

- parse question into slots;
- canonicalize material/regime/property;
- retrieve evidence;
- expand graph path;
- assemble experiment table;
- detect gaps;
- generate grounded answer.

### `evals`

Owns proof:

- gold questions;
- expected evidence spans;
- Recall@10;
- citation coverage;
- unsupported claim count;
- source-label leak checks.

### `frontend`

Owns the server-facing product UI:

- import/status page;
- artifact bank;
- extraction workbench;
- ask/analysis page;
- graph path and neighborhood visualization;
- evidence cards;
- evaluation/security dashboard.

## P0 Screens

### Ingestion

- upload/import files;
- show parser status;
- show extracted artifacts;
- show quarantined sources.

### Ask

- query input;
- filters for material, regime, property, source type, validation status;
- answer summary;
- experiment table;
- evidence cards;
- graph path;
- gaps.

### Evidence

- source document;
- page/row/image reference;
- Markdown snippet;
- structured metadata;
- validation status.

### Evaluation

- run demo questions;
- show Recall@10, citation coverage, unsupported claim count, source-label leaks, and prompt-injection fixture status.

## P0 ID Policy

Use separate identifiers:

- `source_id`: stable raw document identity.
- `artifact_id`: parsed artifact identity.
- `span_id`: stable evidence anchor.
- `extraction_run_id`: mutable parser/extraction run identity.
- `fact_id`: normalized extracted fact identity.
- `claim_id`: answer or effect claim identity.

Rules:

- Never include `extraction_run_id` in `span_id`.
- Generate `source_id` from raw file bytes.
- Generate `span_id` from source ID, artifact type, page/table/row/bbox locator, and normalized visible-content hash.
- Store parser upgrades in `evidence_span_versions` instead of overwriting old evidence.

## P0 Evidence Unit Types

Index and display these separately:

- Markdown section chunk;
- table row;
- table cell;
- extracted fact;
- effect claim;
- material card;
- regime card;
- experiment summary;
- figure caption/OCR;
- decision/conclusion snippet;
- data gap record.

Document chunks alone are insufficient for the materials-science question.

## Answer Assembly Contract

The application prepares an `AllowedEvidencePacket` before the LLM is called:

- query slots;
- allowed experiments;
- measurements;
- effect claims;
- evidence spans;
- graph paths;
- conflicts;
- gaps.

The LLM may only summarize this packet. It cannot introduce facts outside the packet.

Final answer output must be claim-led:

- every sentence has `supporting_span_ids`;
- every experiment-table row has evidence IDs;
- unsupported claim count must be zero for demo answers;
- answers with unsupported claims are blocked or downgraded.

## Build Order

1. Domain schemas and ports.
2. DuckDB schema and migrations.
3. Local artifact memory bank.
4. Docling parser adapter.
5. Stable EvidenceSpan generation.
6. Table-first evidence extraction.
7. Dictionary/rule/entity normalization.
8. EffectClaim and conflict/gap analyzers.
9. Qdrant index and hybrid retrieval.
10. NetworkX graph adapter from DuckDB node/edge tables.
11. QA answer assembler and claim verifier.
12. FastAPI endpoints.
13. React/Vite workbench.
14. Evaluation/security dashboard.
15. Server deployment to `fa.nddev.asia`.

## Deferral List

Do not build before P0 works:

- Neo4j persistence;
- PostgreSQL;
- worker queues;
- full human review workflow;
- MatSciBERT/ChemDataExtractor integration;
- community/global GraphRAG summaries;
- complex ontology expansion.

## Success Criteria

- Demo corpus imports from a clean checkout.
- One ideal demo scenario runs end to end with a polished UI.
- Gold/adversarial fixtures still run through evaluation for regression proof.
- 100% final answer claims cite `EvidenceSpan`.
- At least 80% Recall@10 on demo QA evidence.
- Zero inaccessible evidence in answer context.
- Gap output appears for at least one material-regime-property combination.

## Scale Path

When the demo works:

- promote DuckDB to PostgreSQL for multi-user review and audit;
- promote NetworkX to Neo4j for persistent graph queries and Cypher;
- promote in-process jobs to queue workers;
- promote local artifacts to S3-compatible object storage;
- add domain NLP and review workflow.

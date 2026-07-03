# Architecture

## Architecture Style

Use a modular monolith for the hackathon MVP with replaceable storage adapters. Keep ingestion, graph, retrieval, question answering, and UI separated by explicit service interfaces.

This is faster than microservices and cleaner than a single script. It also allows later extraction of workers, vector service, or graph service without changing product contracts.

## System Context

Inputs:

- internal articles and reports;
- experiment catalog;
- materials and equipment dictionaries;
- employees, teams, labs;
- topic tags and project metadata.

Core services:

- Source Registry;
- Document Parser;
- Artifact Memory Bank;
- Extraction Pipeline;
- Entity Resolution;
- Graph Writer;
- Vector/Hybrid Indexer;
- Query Planner;
- Evidence Assembler;
- Gap Analyzer;
- Extraction Workbench;
- FastAPI API;
- React Workbench.

Stores:

- DuckDB: source registry, ingestion runs, artifacts, evidence spans, facts, graph node/edge tables, answer claims, evaluation, and gap analytics.
- NetworkX: per-query graph path/neighborhood materialization from DuckDB node/edge tables.
- Qdrant: dense plus sparse vectors for chunks, claims, and entity pages.
- Object/file storage: original files, Markdown views, structured parse JSON, extracted tables, extracted images, and manifests.

## Artifact Memory Bank

The MVP should parse every source into an auditable artifact set before extraction:

- `source.pdf` or original file;
- `document.md` for human-readable RAG and quick inspection;
- `document.json` for layout, page, table, image, OCR, and span metadata;
- extracted table files;
- extracted image/figure files;
- `manifest.json` with source checksum, parser version, conversion settings, security label, and artifact checksums.

Markdown is a retrieval and review layer, not the canonical scientific database. Canonical facts live in DuckDB after validation; graph paths are materialized from typed DuckDB node/edge tables.

Artifact parsing has a hard gate: if a source cannot produce stable `EvidenceSpan` IDs for relevant text/table/image regions, it may support exploratory search but cannot support final answer claims.

## Ingestion Flow

1. Source registry stores file metadata, checksum, version, and confidentiality label.
2. Parser extracts text, tables, page numbers, and source spans.
3. Artifact writer creates Markdown, structured JSON, extracted assets, and manifest records.
4. Chunker creates retrieval chunks with document hierarchy and stable source span IDs.
5. Dictionary loader imports known materials, equipment, labs, and tags.
6. Extractor produces candidate entities, claims, measurements, conclusions, and relations.
7. Entity resolution maps candidates to canonical IDs or review tasks.
8. Graph writer persists validated and high-confidence candidates with provenance.
9. Indexer creates dense and sparse searchable records for chunks, claims, and entity summaries.

## Query Flow

1. User question enters Query Planner.
2. Planner extracts structured constraints: material, regime, property, time, lab, equipment, and intent.
3. Exact dictionaries and graph aliases normalize constraints.
4. Source-label filters remove disallowed sources, chunks, claims, graph nodes, and relationships before generation.
5. Hybrid retrieval finds relevant Markdown chunks, structured table rows, claims, and entity pages with payload filters.
6. Graph expansion follows typed paths from retrieved entities.
7. Evidence assembler deduplicates, ranks, and groups facts by experiment and source.
8. Gap analyzer checks expected but missing relationships.
9. Answer generator writes a grounded answer with citations, graph paths, conflicts, and gaps.

## Retrieval Pattern

Use a three-stage retrieval plan:

1. Candidate retrieval: hybrid dense plus sparse search over chunks and claims.
2. Graph expansion: traverse from matching entities to experiments, regimes, measurements, teams, equipment, documents, decisions, and conclusions.
3. Reranking and evidence packing: prefer validated facts, direct measurements, source diversity, exact material/property/regime matches, and recent replicated experiments.

## GraphRAG Pattern

Use GraphRAG selectively:

- Local neighborhood answering for specific alloy/regime/property questions.
- Entity-centric summaries for material or equipment pages.
- Community/global summaries only after enough corpus volume exists.

Avoid using GraphRAG as an opaque summarizer. The graph path and source spans remain the user-facing explanation.

## Failure Modes

- If material or property is ambiguous, return clarification options.
- If no experiment matches all constraints, return nearest matches and explicit gaps.
- If evidence conflicts, show both sides and label the conflict.
- If a source is disallowed by active source-label policy, omit it and explain that restricted evidence exists only if policy allows disclosure.
- If parser quality fails for a document, quarantine that source for review instead of indexing low-confidence spans into final-answer retrieval.

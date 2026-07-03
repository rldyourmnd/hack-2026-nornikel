# Critical Review

Date: 2026-06-28

Scope: planning documents for Nornikel Materials Knowledge Graph and Search.

## Executive Verdict

The direction is correct: evidence-first scientific KG plus hybrid retrieval is better than a plain chatbot, plain GraphRAG, or a graph-only system.

The product will fail, however, if the team tries to build the full architecture at once. The MVP must be a single vertical slice:

```text
artifact memory bank
-> EvidenceSpan
-> material-regime-property-measurement extraction
-> canonical graph path
-> hybrid retrieval
-> cited answer table
-> gap output
```

## Findings

### High: `EvidenceSpan` Was Not First-Class Enough

Confidence: 95

Evidence: Existing docs used `span_id` and source spans but the data and graph model did not explicitly define `EvidenceSpan` as a graph/data entity.

Impact: Final answers could cite vague chunks rather than exact table rows, page regions, or snippets. That breaks the core trust promise.

Fix: Added `EvidenceSpan` to requirements, graph labels, data model, API response, and P0 graph path.

Disposition: must-fix, fixed in planning docs.

### High: MVP Scope Was Too Broad

Confidence: 90

Evidence: The stack included Docling, GROBID, Unstructured, Marker, MinerU, MatSciBERT, ChemDataExtractor, Neo4j, Qdrant, Postgres, React, review queues, timelines, graph visualization, and GraphRAG summaries without strict P0/P1/P2 boundaries.

Impact: The team could spend the hackathon integrating tools while never completing an answerable flow.

Fix: Added P0/P1/P2 boundaries and a critical path. Domain NLP and community GraphRAG are now P2 unless the vertical slice is already stable.

Disposition: must-fix, fixed in planning docs.

### High: Parser Quality Was Under-Specified

Confidence: 90

Evidence: The docs selected Docling as default but had no bakeoff or stop criteria for bad PDFs, scanned images, table-heavy documents, or bilingual sources.

Impact: Bad parse artifacts would poison retrieval and graph extraction.

Fix: Added parser quality gate and quarantine rule. Sources without stable `EvidenceSpan` IDs cannot support final answer claims.

Disposition: must-fix, fixed in planning docs.

### High: Authorization Had To Move Before Generation

Confidence: 85

Evidence: Security docs required object-level labels, but query flow did not explicitly filter retrieval and graph context before LLM context construction.

Impact: Restricted source snippets, filenames, or graph paths could leak through answer generation.

Fix: Added pre-generation source-label filtering and retrieval-layer filtering tests. Full RBAC is deferred because the owner confirmed P0 has open demo access.

Disposition: must-fix, fixed in planning docs.

### Medium: Hybrid Retrieval Needs Explicit Sparse Embedding Generation

Confidence: 85

Evidence: Qdrant supports dense/sparse prefetch plus RRF, but sparse vectors must be generated/configured by the embedding pipeline.

Impact: The team may assume Qdrant automatically provides BM25-like sparse retrieval for arbitrary text.

Fix: Keep BGE-M3/FastEmbed sparse generation as an explicit retrieval pipeline task during implementation.

Disposition: should-fix in scaffold implementation.

### Medium: Neo4j License Needs Productization Decision

Confidence: 80

Evidence: Neo4j Community is GPLv3; Qdrant is Apache-2.0; Docling and MarkItDown are MIT.

Impact: Hackathon demo is fine, but production distribution/commercial packaging needs legal review or a service-bound deployment posture.

Fix: ADR now flags license review. Keep graph adapter replaceable.

Disposition: should-fix before productionization.

### Medium: Local LLM Choice Should Stay Deferred

Confidence: 75

Evidence: Qwen/Mistral choices are plausible, but corpus security policy, GPU availability, Russian/English quality, JSON reliability, and context length are not known.

Impact: Choosing a model too early can block extraction work.

Fix: Provider interface remains mandatory. P0 should run with one configured model plus deterministic validation.

Disposition: should-fix in scaffold implementation.

### High: Initial Infrastructure Was Too Heavy For A Working MVP

Confidence: 90

Evidence: The earlier plan made PostgreSQL, Neo4j, React, worker queues, and object storage part of the first stack.

Impact: The team could spend most of the hackathon on infrastructure and never produce the material-regime-property answer loop.

Fix: MVP now uses DuckDB for metadata/analytics, NetworkX for graph paths, React/Vite for the workbench, FastAPI for contracts, in-process jobs, local artifacts, and Qdrant for retrieval. Postgres, Neo4j, queues, and object storage remain P1 adapters.

Disposition: must-fix, fixed in planning docs.

### High: Evidence Ledger Needed To Be More Concrete

Confidence: 95

Evidence: External review correctly identified that the core system is DuckDB evidence ledger plus Qdrant retrieval, not a RAG app with a side database.

Impact: Without explicit ledger tables, ID policy, and answer claim verification, the scaffold could still drift into opaque LLM answers.

Fix: Added `18_IMPLEMENTATION_SPEC.md`, expanded the MVP blueprint, added answer claim ledger API, and documented ID/confidence/source-label/evaluation contracts.

Disposition: must-fix, fixed in planning docs.

## Must-Have Implementation Gates

1. Parse representative sources into artifact bundles.
2. Generate stable `EvidenceSpan` IDs.
3. Extract at least one material-regime-property-measurement path from PDF/table data.
4. Query returns an experiment table, evidence spans, graph path, and gaps.
5. Every answer claim cites an `EvidenceSpan`.
6. Source-label filtering happens before LLM context construction.
7. Parser failures are quarantined, not silently indexed.

## Working Product Recommendation

Build the first demo around one narrow but complete scientific investigation:

- 1-3 material families;
- 3-5 process regimes;
- 5-10 properties;
- 10-50 source artifacts;
- 10-20 gold questions.

The strongest demo is not a huge graph. It is one credible answer where the user can inspect:

- experiment table;
- source evidence;
- graph path;
- contradiction;
- missing measurement/gap;
- proposed next experiment.

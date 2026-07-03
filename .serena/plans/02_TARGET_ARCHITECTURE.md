# Target Architecture

Date: 2026-07-02
Status: planned (amends `18_IMPLEMENTATION_SPEC.md`; system-of-record rules unchanged)

## Purpose

Define the end-state MVP architecture: components, data flow, schema delta, ports,
and the LLM gateway. Everything here builds on the existing scaffold — no rewrite.

## Component View

```text
React 19/Vite workbench
  ask + filters | artifact bank + ingest status | graph neighborhood (react-force-graph-2d)
  gaps board | conflicts | decisions timeline | eval/security dashboard
        |
FastAPI (services/api)
  /qa/ask  /sources/*  /entities/*  /graph/*  /gaps/*  /eval/*  /health
        |
Application services (src/nornikel_kg/services)
  IngestionService | ExtractionService | EntityResolutionService
  GraphService | RetrievalService | QAService | GapService | ConflictService | EvalService
        |
Ports (src/nornikel_kg/ports)          Adapters (src/nornikel_kg/adapters)
  EvidenceLedgerPort (exists)            duckdb/ (exists, extended)
  DocumentParserPort                     docling/ (PDF text-layer + DOCX + tables)
  UrlFetcherPort                         trafilatura/ (URL -> clean text)
  LLMPort (extract + answer)             llm/ (LiteLLM SDK + Langfuse callback + fake)
  EmbeddingPort                          embeddings/ (sentence-transformers dense + fastembed BM25)
  VectorIndexPort                        qdrant/ (hybrid dense+sparse, RRF)
  GraphStorePort                         networkx/ (built from DuckDB tables)
  ArtifactStorePort                      artifact_fs/ (data/artifacts layout from spec 18)
        |
DuckDB (system of record)   Qdrant (retrieval-only)   Langfuse (observability, separate stack)
```

Rules preserved: domain depends on ports; React calls FastAPI only; if DuckDB and
Qdrant disagree, DuckDB wins; deterministic behavior must survive `LLM_ENABLED=false`.

## Data Flow

### Ingest (upload file or URL)

```text
POST /sources/upload (.pdf .docx .csv .md .txt) | POST /sources/import-url
 -> source registered (source_id = blake3(bytes)), ingestion_run created (status=running)
 -> parse:
      pdf/docx -> Docling (do_ocr=False, do_table_structure=True)
      csv      -> existing CSV path (unchanged)
      md/txt   -> existing text path (unchanged)
      url      -> trafilatura extract -> text artifact
 -> artifacts written under data/artifacts/sources/src_<hash>/ (raw + parsed + manifest)
 -> EvidenceSpans created: text blocks (page + locator), table_row + table_cell spans
    (stable_locator = table_<n>:row_<m>[:col_<k>], bbox when available)
 -> PDF without text layer OR parser failure -> ingestion_run status=quarantined (no spans)
 -> extraction stage (below) -> ingestion_run status=completed with counters
```

### Extraction and auto-linking (the "new links on KB growth" requirement)

```text
for each new text/table EvidenceSpan:
  1. GLiNER (urchade/gliner_multi-v2.1, zero-shot labels: material, processing regime,
     property, equipment, team, person, laboratory, conclusion, decision, value)
     -> entity mentions with char offsets (cheap, no LLM)
  2. LLM guided-JSON extraction per span batch (extraction model, temperature 0):
     experiment slots {material, regime{type,temp_c,duration_h,atmosphere}, property,
     baseline, treated, unit, method, effect_direction} and relations
     {used_equipment, performed_by, authored_by, concluded, derived_from}
     -> Pydantic-validated candidate facts, validation_status='extracted', confidence
     -> invalid JSON => one retry => rule-only fallback (dictionary+regex slots)
  3. Entity resolution (order matters, stop at first hit):
     a. canonical_key exact match (normalize: lower, strip, unify dashes, ё->е)
     b. alias match (dictionaries from resources/dictionaries/*.yml loaded into
        entity_aliases + aliases learned from prior merges)
     c. embedding fallback: cosine >= 0.90 against Qdrant `entities` collection
     d. else create new entity
     Never auto-merge when composition, regime parameters, or equipment identity
     conflict (07_DATA rule).
  4. Merge: append evidence_span_ids, add unseen aliases, write relations
     (each relation carries evidence_span_ids). Measurements/effects flow into the
     existing property_measurements / effect_claims tables (same IDs policy).
  5. Index: upsert evidence units and entity cards into Qdrant (dense+sparse).
```

LLM prompts adapt the MIT-licensed LightRAG extraction prompt structure
(`lightrag/prompt.py`) to our fixed entity/relation types and Russian instructions.

### QA

```text
POST /qa/ask
 -> slot parse: dictionaries + aliases + GLiNER over the question (material/regime/property)
 -> candidate evidence:
      exact slot SQL over ledger (existing path, kept)
      + Qdrant hybrid (dense USER-bge-m3 + sparse BM25, RRF, top-k, payload filter
        security_label + optional source filter) -> rejoin to DuckDB rows
 -> AllowedEvidencePacket (SourceLabelPolicy filter BEFORE packet assembly)
 -> answer synthesis:
      LLM_ENABLED=true: answer model writes Russian sentences as strict JSON
        [{sentence, supporting_span_ids, supporting_fact_ids}], packet-only facts
      LLM_ENABLED=false: existing deterministic template assembler (unchanged)
 -> ClaimVerifier: sentences without valid span IDs are dropped; if any dropped ->
    regenerate once -> otherwise degrade to deterministic assembler (never return
    unsupported text)
 -> conflicts (computed for the selected slots), gaps (coverage query), follow-ups
 -> answer_runs row persisted (replayable run metadata)
```

### Graph

```text
GET /entities/search?q=            (exact + alias + fuzzy over entities)
GET /graph/neighborhood?entity_id=&depth=1|2&limit=
 -> NetworkX MultiDiGraph built on demand from DuckDB (entities, relations,
    experiments, measurements, effects, evidence links) -> nodes/edges JSON with
    types and evidence counts
GET /entities/{id}/timeline        (dated decisions/conclusions/experiments)
```

`/graph/demo-path` is replaced by the real neighborhood endpoint; the answer's
per-experiment `graph_paths` contract in `/qa/ask` is preserved.

## DuckDB Schema Delta (migration 002)

Existing five tables stay untouched. New tables:

| Table | Key columns | Notes |
| --- | --- | --- |
| `ingestion_runs` | run_id PK, source_id, status(running/completed/quarantined/failed), stage, error, counters_json, created_at | powers ingest status UI; quarantine visibility |
| `artifacts` | artifact_id PK, source_id, artifact_type, parser_profile, locator, meta_json | parsed-object registry (spec 18) |
| `entities` | entity_id PK, entity_type, canonical_key, canonical_name, description, metadata_json (composition, dates for decisions), evidence_span_ids_json, confidence, validation_status, created_at, updated_at | decisions/conclusions are entity_type values, not extra tables |
| `entity_aliases` | alias_norm PK(alias_norm, entity_id), entity_id, alias, source(dictionary/learned) | seeded from `resources/dictionaries/*.yml` at migration |
| `relations` | relation_id PK, src_entity_id, relation_type, dst_entity_id, evidence_span_ids_json, confidence, validation_status, created_at | relation_type from the 05_TECH_STACK vocabulary subset |
| `extraction_claims` | claim_id PK, source_id, span_id, payload_json, model_id, status(extracted/accepted/rejected), created_at | raw LLM output audit trail; enables re-processing |
| `answer_runs` | run_id PK, question, filters_json, packet_stats_json, model_id, latency_ms, verification_json, created_at | QA replay + pitch metrics |
| `eval_results` | run_id, question_id, metrics_json, created_at | real numbers behind `/eval/summary` (removes hardcoded 1.0) |

Deliberately NOT added (computed on demand): `conflict_groups`, `data_gaps`,
`retrieval_units` — conflicts/gaps are cheap SQL at MVP scale and materializing them
adds sync burden without demo value.

Relation type subset for MVP (from the `05_TECH_STACK.md` vocabulary): `MADE_OF`,
`APPLIES_REGIME`, `HAS_MEASUREMENT`, `OF_PROPERTY`, `PRODUCED_EFFECT`,
`USED_EQUIPMENT`, `PERFORMED_BY`, `AUTHORED_BY`, `SUPPORTED_BY`, `FROM_DOCUMENT`,
`DERIVED_FROM`, `CONTRADICTS` (+ `CONCLUDES` for decision/conclusion entities).

## LLM Gateway Design

One module (`adapters/llm/gateway.py`) is the only place that imports litellm:

- Model aliases from env: `LLM_EXTRACTION_MODEL`, `LLM_ANSWER_MODEL` (LiteLLM strings,
  e.g. `openai/<catalog-model-id>` with `api_base=DATAEYES_API_BASE`,
  `api_key=DATAEYES_API_KEY`; Ollama route `ollama_chat/<model>` as fallback).
- `response_format` JSON schema for extraction; temperature 0; max_tokens caps;
  request timeout + 1 retry; per-run token budget guard (hard stop + log).
- Langfuse: `litellm.success_callback=["langfuse"]` / `failure_callback`, env
  `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`, `metadata={trace_id: <run_id>, tags: [stage]}`
  so every ingest/QA run is traceable end-to-end. Pin `langfuse==2.59.x` (SDK v2
  callback path; server v3 accepts it).
- `LLM_ENABLED=false` (default in CI/tests) switches to `FakeLLM` deterministic
  adapter with canned fixture outputs — every pipeline stays testable offline.

## Embeddings

- Dense: `deepvk/USER-bge-m3` via sentence-transformers, CPU (torch is already a
  Docling dependency — no extra heavy stack). 1024-dim, cosine.
- Sparse: `Qdrant/bm25` via fastembed (IDF modifier on the Qdrant collection).
- Qdrant collections: `evidence_units` (named dense + sparse vectors; payload:
  span_id, source_id, span_type, security_label, material/property/regime ids) and
  `entities` (dense only; payload: entity_id, entity_type) for resolution fallback.
- Hybrid query: `query_points` with dense+sparse `Prefetch` + `FusionQuery(RRF)`.
- No reranker in MVP (candidate sets are small; deterministic slot-match reranking
  from spec 18 applies instead). Extension point documented.

## Frontend Delta (FSD layout)

| Widget/feature | Location | Notes |
| --- | --- | --- |
| Graph neighborhood | `widgets/graph-view` (rewrite) | `react-force-graph-2d`; node color by entity_type, click -> expand neighbors, side panel with evidence links |
| Ingest status | `widgets/artifact-bank` (extend) | per-source run status chip incl. quarantined; poll while running |
| Gaps board | `widgets/gaps-board` (new) | material x regime x property coverage matrix; empty cells -> clickable gap queries |
| Conflicts | `widgets/analysis-workbench` (extend) | conflict cards with both sides' evidence |
| Decisions timeline | `widgets/timeline` (new) | dated decision/conclusion entities with evidence links |
| Eval dashboard | `widgets/evaluation-dashboard` (extend) | real metrics from `/eval/summary` + last eval run date |

New frontend dependency: `react-force-graph-2d` only (verify React 19 peer range at
install; fallback `reagraph` — decision point in W4, see critical review R7).

## Extension Points (documented, not built)

Postgres via MetadataStore port; Neo4j via GraphStore port; queue workers for
ingestion stages; S3 artifact store; reranker (`bge-reranker-v2-m3`); review-queue UI
over `extraction_claims.status`; OCR pipeline profile for scanned PDFs.

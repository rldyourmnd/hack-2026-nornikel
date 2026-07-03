# P0 Implementation Specification

## Purpose

This file is the implementation source of truth for the first scaffold. It integrates the external review and supersedes any broader P1/productization ideas when there is a conflict.

## P0 Verdict

Build an evidence ledger first, not a chatbot and not a full production KG stack.

```text
Artifact memory bank
-> stable EvidenceSpans
-> table/fact extraction
-> DuckDB scientific evidence ledger
-> Qdrant hybrid candidate retrieval
-> NetworkX graph path rendering
-> deterministic evidence packet
-> LLM summary with claim verification
-> evaluation/security dashboard
```

## Hard Boundaries

- DuckDB is the P0 system of record.
- Qdrant is retrieval only.
- NetworkX is graph materialization only.
- React/Vite is the P0 UI and must call FastAPI contracts.
- Markdown is a convenience view, not truth.
- Tables, table rows, and table cells are first-class evidence.
- Every final answer sentence must cite `EvidenceSpan` IDs.
- Source security-label filtering happens before Qdrant context enters the LLM packet and is rechecked after retrieval.
- External LLM and embedding APIs are allowed through LiteLLM/OpenAI-compatible providers, configured only by environment variables and server secrets.

## Required Ports

Keep these swappable:

- `DocumentParserPort`: Docling now, other parsers later.
- `ArtifactStorePort`: local filesystem now, object storage later.
- `MetadataStorePort`: DuckDB now, PostgreSQL later.
- `VectorIndexPort`: Qdrant now, alternative retrieval store later.
- `GraphStorePort`: DuckDB edge tables plus NetworkX now, Neo4j later.
- `EmbeddingModelPort`: LiteLLM/OpenAI-compatible provider now, local/FastEmbed fallback later.
- `SparseEncoderPort`: BM25/SPLADE/miniCOIL/BGE-M3-style sparse encoder can change.
- `LLMExtractorPort`: provider/local model can change.
- `SecurityLabelPolicyPort`: open demo access plus source labels now, enterprise IAM later.
- `EvaluationStorePort`: DuckDB now, experiment tracking later.

Do not over-abstract the core domain services:

- `EvidenceSpanFactory`;
- `TableEvidenceBuilder`;
- `MaterialNormalizer`;
- `RegimeNormalizer`;
- `MeasurementNormalizer`;
- `ConflictDetector`;
- `GapAnalyzer`;
- `AnswerAssembler`;
- `ClaimVerifier`.

## Identifier Policy

Separate these IDs:

- `source_id`: stable raw document identity.
- `artifact_id`: parsed object identity.
- `span_id`: stable evidence anchor.
- `extraction_run_id`: mutable parser/extraction run identity.
- `fact_id`: normalized extracted fact identity.
- `claim_id`: extraction or answer claim identity.

Recommended formulas:

```text
source_id = "src_" + blake3(raw_file_bytes)[0:16]

artifact_id = "art_" + blake3(
  source_id + artifact_type + parser_profile + artifact_locator
)[0:16]

span_id = "evs_" + blake3(
  source_id
  + artifact_type
  + page_index
  + stable_locator
  + quantized_bbox
  + normalized_visible_content_hash
)[0:20]
```

Do not include `extraction_run_id` in `span_id`.

## Artifact Layout

```text
data/artifacts/
└── sources/
    └── src_<hash>/
        ├── raw/
        │   └── original.ext
        ├── manifest.json
        ├── docling/
        │   ├── document.json
        │   └── document.md
        ├── pages/
        ├── tables/
        │   ├── table_0001.json
        │   ├── table_0001.parquet
        │   └── table_0001.csv
        ├── figures/
        ├── chunks/
        │   ├── markdown_chunks.jsonl
        │   ├── table_row_units.jsonl
        │   └── figure_units.jsonl
        └── extraction/
            └── extraction_run_<id>.jsonl
```

## Minimum DuckDB Tables

- `sources`;
- `source_security_labels`;
- `ingestion_runs`;
- `artifacts`;
- `evidence_spans`;
- `evidence_span_versions`;
- `tables`;
- `table_rows`;
- `table_cells`;
- `figures`;
- `entities`;
- `materials`;
- `processing_regimes`;
- `process_steps`;
- `properties`;
- `experiments`;
- `measurements`;
- `effect_claims`;
- `conflict_groups`;
- `data_gaps`;
- `graph_nodes`;
- `graph_edges`;
- `retrieval_units`;
- `answer_runs`;
- `answer_claims`;
- `eval_questions`;
- `eval_results`;
- `security_check_results`.

## Required Schemas

### EvidenceSpan

```json
{
  "span_id": "evs_...",
  "source_id": "src_...",
  "artifact_id": "art_...",
  "span_type": "text|table_row|table_cell|figure|page_image",
  "page": 6,
  "locator": {},
  "visible_text": "...",
  "extraction_run_id": "ing_...",
  "validation_status": "raw|extracted|normalized|validated_rule|validated_manual|rejected|conflict|needs_review",
  "evidence_confidence": 0.92
}
```

### ProcessingRegime

```json
{
  "regime_id": "reg_...",
  "regime_type": "annealing|aging|cold_rolling|hot_rolling|casting|welding|HIP|quenching|solution_treatment",
  "steps": [
    {
      "step_index": 1,
      "operation": "aging",
      "temperature": {"value": 700, "unit": "C"},
      "duration": {"value": 8, "unit": "h"},
      "atmosphere": "air",
      "cooling": "water_quench"
    }
  ]
}
```

### PropertyMeasurement

```json
{
  "measurement_id": "meas_...",
  "experiment_id": "exp_...",
  "property_id": "prop_hardness",
  "value": 245,
  "unit": "HV",
  "original_value": "245 HV",
  "method": "Vickers",
  "test_conditions": {},
  "supporting_span_ids": ["evs_..."],
  "confidence": {
    "evidence": 0.96,
    "extraction": 0.94,
    "normalization": 0.88
  },
  "validation_status": "validated_rule"
}
```

### EffectClaim

```json
{
  "effect_id": "eff_...",
  "experiment_id": "exp_...",
  "material_id": "mat_...",
  "regime_id": "reg_...",
  "property_id": "prop_hardness",
  "direction": "increase|decrease|no_change|mixed|unknown",
  "delta_value": 35,
  "delta_unit": "HV",
  "baseline_measurement_id": "meas_...",
  "treated_measurement_id": "meas_...",
  "qualitative_only": false,
  "qualitative_summary": "Hardness increased after aging at 700 C for 8 h.",
  "supporting_span_ids": ["evs_..."],
  "comparability_notes": "Same method, same material, different aging time."
}
```

## Table Evidence Rules

P0 must create:

- `Table`;
- `TableRowEvidenceSpan`;
- `TableCellEvidenceSpan`.

Each table stores:

- caption;
- page;
- table bounding box;
- original cell grid;
- row/column spans;
- normalized headers;
- inferred units;
- row-wise Markdown;
- row-wise JSON;
- cell bounding boxes;
- extraction confidence.

Index table rows separately. A table row is the most important retrieval unit for numeric material-property questions.

## Retrieval Pipeline

1. Parse user query into material/regime/property candidates.
2. Resolve canonical entities and aliases from DuckDB dictionaries.
3. Resolve source security-label policy into allowed source/span IDs.
4. Run Qdrant retrieval with mandatory source/security-label payload filters.
5. Retrieve dense and sparse candidates; use RRF when both are available.
6. Rejoin candidate retrieval units back to DuckDB.
7. Drop any unit whose source/span is not allowed.
8. Expand to adjacent evidence: same table row, neighboring rows, caption, experiment summary, graph path.
9. Rerank with deterministic features.
10. Assemble answer only from validated facts/evidence.

## Reranking Features

Positive features:

- exact material match;
- material alias match;
- composition overlap;
- exact property match;
- property synonym match;
- regime type match;
- regime parameter match;
- table row or fact unit boost;
- validation status boost;
- evidence confidence boost;
- same experiment cluster;
- Results/Tables section boost;
- unit/method match.

Negative features:

- low OCR confidence;
- unsupported LLM-only claim;
- Security-label uncertainty hard reject.

## Graph Model

P0 canonical path:

```text
(Experiment)-[:USES_SAMPLE]->(Sample)
(Sample)-[:MADE_OF]->(Material)
(Material)-[:HAS_COMPOSITION]->(MaterialComposition)
(Experiment)-[:APPLIES_REGIME]->(ProcessingRegime)
(ProcessingRegime)-[:HAS_STEP]->(ProcessStep)
(Experiment)-[:HAS_MEASUREMENT]->(PropertyMeasurement)
(PropertyMeasurement)-[:OF_PROPERTY]->(Property)
(PropertyMeasurement)-[:SUPPORTED_BY]->(EvidenceSpan)
(EffectClaim)-[:COMPARES_BASELINE]->(PropertyMeasurement)
(EffectClaim)-[:COMPARES_TREATED]->(PropertyMeasurement)
(EvidenceSpan)-[:FROM_DOCUMENT]->(Document)
```

Store graph nodes and edges in DuckDB; build NetworkX `MultiDiGraph` per query.

Switch to Neo4j only after P0 works and graph queries, graph size, multi-user exploration, or persistent Cypher usage justify it.

## Answer Assembly

The LLM receives only an `AllowedEvidencePacket`:

- query slots;
- experiments;
- measurements;
- effect claims;
- evidence spans;
- graph paths;
- conflicts;
- gaps.

Required answer structure:

```json
{
  "answer_summary": [
    {
      "sentence": "...",
      "supporting_span_ids": ["evs_..."],
      "supporting_fact_ids": ["meas_..."],
      "graph_path_ids": ["path_..."]
    }
  ],
  "experiment_table": [],
  "conflicts": [],
  "gaps": [],
  "limitations": []
}
```

No support IDs means no sentence.

## Security Gates

Minimum P0:

- resolve allowed sources/spans before retrieval;
- apply Qdrant payload security-label filters;
- recheck source/span IDs after retrieval;
- build LLM context only from allowed evidence;
- mark prompt-injection-like spans as suspicious, not deleted;
- wrap source evidence as untrusted data;
- run adversarial fixtures.

Pass thresholds:

- `source_label_leak_count = 0`;
- `restricted_source_in_context_count = 0`;
- `prompt_injection_success_count = 0`;
- `system_prompt_leak_count = 0`.

## Evaluation Thresholds

For a curated hackathon corpus:

- EvidenceRecall@10 >= 80%;
- EvidenceRecall@20 >= 90%;
- TableRowRecall@10 >= 75%;
- citation coverage >= 95%;
- unsupported claim count = 0 on demo questions;
- source-label leaks = 0;
- numeric value + unit accuracy >= 85%;
- effect direction accuracy >= 80%;
- entity resolution accuracy >= 85% for curated aliases;
- gap detection precision >= 80%.

## P0 UI Screens

Required:

1. Source import and ingestion status.
2. Artifact memory bank.
3. Extraction workbench.
4. Ask/analysis workbench.
5. Evidence cards.
6. Graph path/neighborhood.
7. Evaluation/security dashboard.

Omit:

- login/admin system;
- ontology editor;
- arbitrary chat history;
- full review workflow;
- Neo4j browser;
- chart digitization;
- LLM agent tools.

## 72-Hour Build Plan

0-4h: lock scope, fixtures, gold questions.

4-8h: repository scaffold, `pyproject.toml`, `Makefile`, basic package layout.

8-16h: Docling ingestion and artifact bank.

16-24h: DuckDB schema and evidence registry.

24-32h: dictionary/rule/table extraction.

32-40h: Qdrant indexing and retrieval.

40-48h: QA pipeline and claim verifier.

48-54h: graph path builder.

54-62h: React/Vite workbench.

62-68h: evaluation and security gates.

68-72h: demo polish.

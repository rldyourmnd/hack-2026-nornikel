# API Design

## Principles

- API returns structured evidence, not only generated text.
- All search and answer responses include reproducibility IDs.
- Generated answers are derived views over retrieved evidence.
- Internal IDs are stable and opaque.

## Core Endpoints

### Sources

- `POST /sources`: register uploaded or referenced source.
- `GET /sources`: list sources with filters.
- `GET /sources/{source_id}`: source metadata and import status.
- `GET /sources/{source_id}/spans/{span_id}`: source snippet or table cell reference.

### Ingestion

- `POST /ingestion/jobs`: start import/extraction/indexing job.
- `GET /ingestion/jobs/{job_id}`: job status, errors, counters.
- `POST /ingestion/jobs/{job_id}/retry`: retry failed stages.

### Entities

- `GET /entities/search`: exact and fuzzy entity lookup.
- `GET /entities/{entity_id}`: canonical entity page.
- `GET /entities/{entity_id}/neighbors`: graph neighborhood.
- `GET /entities/{entity_id}/timeline`: dated experiments, decisions, and documents.

### Search

- `POST /search/hybrid`: hybrid search over chunks, claims, and entity summaries.
- `POST /search/graph`: constrained graph traversal.
- `POST /search/facets`: available filters for current query.

### Question Answering

- `POST /qa/ask`: answer with evidence, graph paths, conflicts, and gaps.
- `GET /qa/runs/{run_id}`: replayable retrieval and answer metadata.
- `GET /qa/runs/{run_id}/claims`: answer claim ledger with support IDs and verification status.

### Review

- `GET /review/items`: candidate facts requiring validation.
- `POST /review/items/{item_id}/approve`: approve fact.
- `POST /review/items/{item_id}/reject`: reject fact with reason.
- `POST /review/items/{item_id}/merge`: merge duplicate entity candidates.

### Gaps

- `POST /gaps/analyze`: compute gaps for filters.
- `GET /gaps`: list known data gaps.
- `POST /gaps/{gap_id}/decision`: record decision or follow-up.

## `POST /qa/ask` Request

```json
{
  "question": "What was done for alloy X under regime Y and how did property Z change?",
  "language": "ru",
  "filters": {
    "material": ["Ni-30Cu"],
    "property": ["Vickers hardness"],
    "regime": ["aging 700C"],
    "source_id": ["src_..."],
    "regime_id": ["reg_..."]
  },
  "include_graph": true,
  "include_gaps": true
}
```

## `POST /qa/ask` Response

```json
{
  "run_id": "qa_run_...",
  "answer_summary": [
    {
      "sentence": "Aging at 700 C for 8 h increased Vickers hardness for Ni-30Cu in the accessible evidence.",
      "supporting_span_ids": ["evs_..."],
      "supporting_fact_ids": ["meas_..."],
      "graph_path_ids": ["path_..."]
    }
  ],
  "confidence": "medium",
  "experiments": [
    {
      "experiment_id": "exp_...",
      "material_id": "mat_...",
      "material_name": "Ni-30Cu",
      "regime_id": "reg_...",
      "regime_summary": "Annealing, 900 C, 2 h, Ar",
      "property_id": "prop_...",
      "property_name": "Vickers hardness",
      "measurement": {
        "value": 320,
        "unit": "HV",
        "delta_percent": 12,
        "effect_direction": "increase"
      },
      "evidence_ids": ["span_..."],
      "validation_status": "validated"
    }
  ],
  "evidence": [
    {
      "source_id": "src_...",
      "span_id": "span_...",
      "span_type": "table_row",
      "page": 8,
      "table_id": "table_002",
      "row_id": "row_005",
      "entity_ids": ["exp_...", "mat_..."],
      "claim_id": "claim_...",
      "validation_status": "validated"
    }
  ],
  "graph_paths": [
    {
      "nodes": ["exp_...", "sample_...", "mat_...", "reg_...", "step_...", "measure_...", "prop_...", "span_...", "src_..."],
      "relationships": ["USES_SAMPLE", "MADE_OF", "APPLIES_REGIME", "HAS_STEP", "HAS_MEASUREMENT", "OF_PROPERTY", "SUPPORTED_BY", "FROM_DOCUMENT"]
    }
  ],
  "verification": {
    "citation_coverage": 1.0,
    "unsupported_claim_count": 0,
    "source_label_leak_count": 0
  },
  "conflicts": [],
  "gaps": [
    {
      "type": "missing_measurement",
      "description": "No validated measurement found for property Z under exact regime Y."
    }
  ],
  "follow_up_queries": []
}
```

## Error Rules

- Ambiguous material or property returns `409` with candidate entities.
- Disallowed source-label access returns `403` when a policy is active; otherwise the answer must omit disallowed evidence.
- Missing evidence returns `200` with empty evidence and explicit gaps, not a hallucinated answer.
- Generated sentences without support IDs are rejected before the final response is returned.

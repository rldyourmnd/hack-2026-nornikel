CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  error TEXT,
  counters_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  parser_profile TEXT NOT NULL,
  locator TEXT NOT NULL,
  meta_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  description TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  evidence_span_ids_json TEXT NOT NULL DEFAULT '[]',
  confidence DOUBLE NOT NULL DEFAULT 1.0,
  validation_status TEXT NOT NULL DEFAULT 'validated',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  alias_norm TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  alias TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'dictionary',
  PRIMARY KEY (alias_norm, entity_id)
);

CREATE TABLE IF NOT EXISTS relations (
  relation_id TEXT PRIMARY KEY,
  src_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  dst_entity_id TEXT NOT NULL,
  evidence_span_ids_json TEXT NOT NULL DEFAULT '[]',
  confidence DOUBLE NOT NULL DEFAULT 1.0,
  validation_status TEXT NOT NULL DEFAULT 'extracted',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extraction_claims (
  claim_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  span_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  model_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'extracted',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answer_runs (
  run_id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  filters_json TEXT NOT NULL DEFAULT '{}',
  packet_stats_json TEXT NOT NULL DEFAULT '{}',
  model_id TEXT,
  latency_ms INTEGER,
  verification_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eval_results (
  run_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

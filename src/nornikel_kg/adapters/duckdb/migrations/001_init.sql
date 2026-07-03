CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  document_type TEXT NOT NULL DEFAULT 'report',
  raw_sha256 TEXT NOT NULL,
  security_label TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_spans (
  span_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  span_type TEXT NOT NULL,
  visible_text TEXT NOT NULL,
  page INTEGER,
  locator_json TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  evidence_confidence DOUBLE NOT NULL,
  security_label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS property_measurements (
  measurement_id TEXT PRIMARY KEY,
  source_id TEXT,
  experiment_id TEXT NOT NULL,
  property_id TEXT NOT NULL,
  property_name TEXT NOT NULL,
  value DOUBLE,
  unit TEXT,
  original_value TEXT,
  method TEXT,
  supporting_span_ids_json TEXT NOT NULL,
  validation_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS effect_claims (
  effect_id TEXT PRIMARY KEY,
  source_id TEXT,
  experiment_id TEXT NOT NULL,
  material_id TEXT NOT NULL,
  material_name TEXT,
  regime_id TEXT NOT NULL,
  regime_summary TEXT,
  property_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  supporting_span_ids_json TEXT NOT NULL,
  baseline_measurement_id TEXT,
  treated_measurement_id TEXT,
  delta_value DOUBLE,
  delta_unit TEXT,
  qualitative_only BOOLEAN NOT NULL,
  qualitative_summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answer_claims (
  answer_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  supporting_span_ids_json TEXT NOT NULL,
  supporting_fact_ids_json TEXT NOT NULL,
  graph_path_ids_json TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

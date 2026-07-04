-- Persisted generic numeric-fact layer.
-- Real corpus tables (water chemistry, phase distribution, techno-economics)
-- carry subject + measured value + unit. Facts are extracted from headered
-- table rows at ingest and linked back to their evidence span, so constrained
-- QA can SQL-filter by subject/property/unit/value instead of re-parsing span
-- text at query time. Idempotent: the migration runner re-executes every file
-- on each process start (no applied-migrations table).
CREATE TABLE IF NOT EXISTS numeric_facts (
  fact_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  span_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  subject_label TEXT NOT NULL,
  prop TEXT NOT NULL,
  value DOUBLE NOT NULL,
  unit TEXT NOT NULL DEFAULT '',
  qualifier TEXT NOT NULL DEFAULT '',
  confidence DOUBLE NOT NULL DEFAULT 1.0,
  validation_status TEXT NOT NULL DEFAULT 'candidate',
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_numeric_facts_source ON numeric_facts(source_id);
CREATE INDEX IF NOT EXISTS idx_numeric_facts_span ON numeric_facts(span_id);
CREATE INDEX IF NOT EXISTS idx_numeric_facts_subject ON numeric_facts(subject);
CREATE INDEX IF NOT EXISTS idx_numeric_facts_prop ON numeric_facts(prop);

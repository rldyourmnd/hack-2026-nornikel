-- Indexes for depth-limited SQL graph-neighborhood traversal, replacing the
-- full NetworkX materialization on every /graph/neighborhood call. The relations
-- table previously had only its relation_id primary-key index, so each hop was a
-- full scan. Idempotent (the migration runner re-executes every file per start).
CREATE INDEX IF NOT EXISTS idx_relations_src ON relations(src_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_dst ON relations(dst_entity_id);

CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);

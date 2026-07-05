export type EvidenceSpan = {
  span_id: string;
  source_id: string;
  artifact_id: string;
  span_type: "text" | "table_row" | "table_cell" | "figure" | "page_image";
  visible_text: string;
  page: number | null;
  locator: Record<string, unknown>;
  validation_status: string;
  evidence_confidence: number;
  security_label: string;
};

export type SourceSummary = {
  source_id: string;
  title: string;
  document_type: string;
  security_label: string;
  status: string;
  evidence_count: number;
  measurement_count: number;
  year: number | null;
  geography: string | null;
};

export type SourceIngestResponse = {
  source: SourceSummary;
  evidence_count: number;
  measurement_count: number;
  warnings: string[];
};

export type ArchiveMemberResult = {
  member_path: string;
  status: string;
  reason_code: string | null;
  source_id: string | null;
};

export type ArchiveUploadResponse = {
  archive: string;
  member_count: number;
  ingested_count: number;
  members: ArchiveMemberResult[];
  expansion_stats: Record<string, number>;
};

export type AnswerSentence = {
  sentence: string;
  supporting_span_ids: string[];
  supporting_fact_ids: string[];
  graph_path_ids: string[];
};

export type ExperimentRow = {
  experiment_id: string;
  material_name: string;
  regime_summary: string;
  property_name: string;
  measurement: Record<string, unknown>;
  evidence_ids: string[];
  validation_status: string;
};

export type GraphPath = {
  path_id: string;
  nodes: string[];
  relationships: string[];
};

export type AskResponse = {
  run_id: string;
  answer_summary: AnswerSentence[];
  confidence: "low" | "medium" | "high";
  experiments: ExperimentRow[];
  evidence: EvidenceSpan[];
  graph_paths: GraphPath[];
  verification: {
    citation_coverage: number;
    unsupported_claim_count: number;
    source_label_leak_count: number;
    prompt_injection_success_count: number;
    numeric_mismatch_count: number;
    semantic_unsupported_count: number;
  };
  conflicts: Array<Record<string, unknown>>;
  gaps: Array<Record<string, unknown>>;
  follow_up_queries: string[];
};

export type AskFilters = {
  source_ids?: string[];
  material_name?: string[];
  property_name?: string[];
  regime_summary?: string[];
  experiment_id?: string[];
  regime_id?: string[];
  material?: string[];
  property?: string[];
  regime?: string[];
  source_id?: string[];
  geography?: string[];
  year_from?: number;
  year_to?: number;
};

export type AskRequest = {
  question: string;
  language?: "ru" | "en";
  include_graph?: boolean;
  include_gaps?: boolean;
  filters?: AskFilters;
  allowed_labels?: Array<"public" | "internal" | "confidential" | "restricted">;
};

export type GraphNode = {
  entity_id: string;
  entity_type: string;
  label: string;
  evidence_count: number;
};

export type GraphEdge = {
  relation_id: string;
  source: string;
  target: string;
  relation_type: string;
  evidence_count: number;
};

export type GraphNeighborhood = {
  focus_entity_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type EntitySearchResult = {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
};

export type TypedEntity = {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
  evidence_count: number;
};

export type GapCell = {
  material_id: string;
  material_name: string;
  regime_type: string;
  regime_name: string;
  property_id: string;
  property_name: string;
  covered: boolean;
  experiment_ids: string[];
};

export type GapsAnalysis = {
  materials: string[];
  regimes: string[];
  properties: string[];
  cells: GapCell[];
  gap_count: number;
  covered_count: number;
};

export type TimelineEvent = {
  entity_id: string;
  entity_type: string;
  title: string;
  date: string | null;
  year: number | null;
  evidence_span_ids: string[];
};

export type StatsOverview = {
  sources: number;
  evidence_spans: number;
  measurements: number;
  numeric_facts: number;
  numeric_facts_by_unit: Record<string, number>;
  numeric_facts_by_subject: Record<string, number>;
  relations: number;
  answer_runs: number;
  entities_by_type: Record<string, number>;
  relations_by_type: Record<string, number>;
  security_labels: Record<string, number>;
  quarantined: number;
  quarantine_reasons: Record<string, number>;
};

export type AnswerRunSummary = {
  run_id: string;
  question: string;
  answer_mode: string | null;
  latency_ms: number | null;
  verification: Record<string, number>;
  created_at: string;
};

export type EvalSummary = {
  status: string;
  run_id?: string;
  run_at?: string;
  question_count?: number;
  metrics: Record<string, number>;
};

export type HealthStatus = {
  status: string;
  version: string;
  llm_enabled: boolean;
  llm_configured: boolean;
  embedding_backend: string;
};

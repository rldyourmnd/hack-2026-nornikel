from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SecurityLabel = Literal["public", "internal", "confidential", "restricted"]
ValidationStatus = Literal[
    "raw",
    "extracted",
    "normalized",
    "validated_rule",
    "validated_manual",
    "rejected",
    "conflict",
    "needs_review",
]
SpanType = Literal["text", "table_row", "table_cell", "figure", "page_image"]
EffectDirection = Literal["increase", "decrease", "no_change", "mixed", "unknown"]


class EvidenceSpan(BaseModel):
    span_id: str
    source_id: str
    artifact_id: str
    span_type: SpanType
    visible_text: str
    page: int | None = None
    locator: dict[str, object] = Field(default_factory=dict)
    extraction_run_id: str | None = None
    validation_status: ValidationStatus = "raw"
    evidence_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    security_label: SecurityLabel = "internal"


class SourceSummary(BaseModel):
    source_id: str
    title: str
    document_type: str
    security_label: SecurityLabel
    status: str
    evidence_count: int = 0
    measurement_count: int = 0
    year: int | None = None
    geography: str | None = None


class SourceIngestResponse(BaseModel):
    source: SourceSummary
    evidence_count: int
    measurement_count: int
    warnings: list[str] = Field(default_factory=list)


class Material(BaseModel):
    material_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    alloy_family: str = "unknown"
    composition: list[dict[str, object]] = Field(default_factory=list)


class ProcessStep(BaseModel):
    step_index: int
    operation: str
    temperature_c: float | None = None
    duration_h: float | None = None
    atmosphere: str | None = None
    cooling: str | None = None
    deformation_percent: float | None = None


class ProcessingRegime(BaseModel):
    regime_id: str
    regime_type: str
    summary: str
    steps: list[ProcessStep] = Field(default_factory=list)


class PropertyMeasurement(BaseModel):
    measurement_id: str
    experiment_id: str
    property_id: str
    property_name: str
    value: float | None = None
    unit: str | None = None
    original_value: str | None = None
    method: str | None = None
    supporting_span_ids: list[str]
    validation_status: ValidationStatus = "validated_rule"


class EffectClaim(BaseModel):
    effect_id: str
    experiment_id: str
    material_id: str
    regime_id: str
    property_id: str
    direction: EffectDirection
    supporting_span_ids: list[str]
    baseline_measurement_id: str | None = None
    treated_measurement_id: str | None = None
    delta_value: float | None = None
    delta_unit: str | None = None
    qualitative_only: bool = False
    qualitative_summary: str


class ExperimentRow(BaseModel):
    experiment_id: str
    source_id: str | None = None
    material_id: str
    material_name: str
    regime_id: str
    regime_summary: str
    property_id: str
    property_name: str
    measurement: dict[str, object]
    evidence_ids: list[str]
    validation_status: ValidationStatus


class GraphPath(BaseModel):
    path_id: str
    nodes: list[str]
    relationships: list[str]


class AnswerSentence(BaseModel):
    sentence: str
    supporting_span_ids: list[str]
    supporting_fact_ids: list[str] = Field(default_factory=list)
    graph_path_ids: list[str] = Field(default_factory=list)


class AnswerVerification(BaseModel):
    citation_coverage: float
    unsupported_claim_count: int
    source_label_leak_count: int
    prompt_injection_success_count: int = 0
    # Sentences whose numbers do not literally appear in their cited spans.
    numeric_mismatch_count: int = 0
    # Sentences whose content words / polarity are not supported by their cited
    # spans (rule-based semantic-overlap + negation-parity check).
    semantic_unsupported_count: int = 0


class AskFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(default_factory=list)
    source_id: list[str] = Field(default_factory=list)
    material_name: list[str] = Field(default_factory=list)
    material: list[str] = Field(default_factory=list)
    property_name: list[str] = Field(default_factory=list)
    property: list[str] = Field(default_factory=list)
    regime_summary: list[str] = Field(default_factory=list)
    regime: list[str] = Field(default_factory=list)
    experiment_id: list[str] = Field(default_factory=list)
    regime_id: list[str] = Field(default_factory=list)
    # Track requirements: geography (ru/foreign) and publication-year window.
    geography: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None

    @field_validator(
        "source_ids",
        "source_id",
        "material_name",
        "material",
        "property_name",
        "property",
        "regime_summary",
        "regime",
        "experiment_id",
        "regime_id",
        "geography",
        mode="before",
    )
    @classmethod
    def _coerce_filter_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            return [value] if value else []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, bool):
            raise ValueError("Filter values must be string or list of strings.")
        return [str(value)] if str(value).strip() else []


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    language: Literal["ru", "en"] = "ru"
    include_graph: bool = True
    include_gaps: bool = True
    filters: AskFilters = Field(default_factory=AskFilters)
    # Optional visibility narrowing (e.g. jury/external mode = ["public",
    # "internal"]). A request may only NARROW the deployment policy, never widen
    # it; None keeps the deployment default.
    allowed_labels: list[SecurityLabel] | None = None


class AskResponse(BaseModel):
    run_id: str
    answer_summary: list[AnswerSentence]
    confidence: Literal["low", "medium", "high"]
    experiments: list[ExperimentRow]
    evidence: list[EvidenceSpan]
    graph_paths: list[GraphPath]
    verification: AnswerVerification
    conflicts: list[dict[str, object]] = Field(default_factory=list)
    gaps: list[dict[str, object]] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)

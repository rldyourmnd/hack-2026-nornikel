from __future__ import annotations

from collections.abc import Sequence

from nornikel_kg.domain.ids import artifact_id, span_id
from nornikel_kg.domain.models import EvidenceSpan, SecurityLabel, SpanType, ValidationStatus


class EvidenceSpanFactory:
    def create(
        self,
        *,
        source_id: str,
        artifact_type: str,
        parser_profile: str,
        artifact_locator: str,
        span_type: SpanType,
        visible_text: str,
        page: int | None = None,
        stable_locator: str,
        bbox: Sequence[float] | None = None,
        validation_status: ValidationStatus = "raw",
        evidence_confidence: float = 1.0,
        security_label: SecurityLabel = "internal",
        extraction_run_id: str | None = None,
        locator_extra: dict[str, object] | None = None,
    ) -> EvidenceSpan:
        computed_artifact_id = artifact_id(
            source_id=source_id,
            artifact_type=artifact_type,
            parser_profile=parser_profile,
            artifact_locator=artifact_locator,
        )
        computed_span_id = span_id(
            source_id=source_id,
            artifact_type=artifact_type,
            page_index=page,
            stable_locator=stable_locator,
            visible_text=visible_text,
            bbox=bbox,
        )
        return EvidenceSpan(
            span_id=computed_span_id,
            source_id=source_id,
            artifact_id=computed_artifact_id,
            span_type=span_type,
            visible_text=visible_text,
            page=page,
            locator={
                "stable_locator": stable_locator,
                "bbox": list(bbox) if bbox else None,
                **(locator_extra or {}),
            },
            extraction_run_id=extraction_run_id,
            validation_status=validation_status,
            evidence_confidence=evidence_confidence,
            security_label=security_label,
        )

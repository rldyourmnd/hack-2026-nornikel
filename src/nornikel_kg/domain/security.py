from __future__ import annotations

from dataclasses import dataclass

from nornikel_kg.domain.models import EvidenceSpan, SecurityLabel

DEFAULT_ALLOWED_LABELS: frozenset[SecurityLabel] = frozenset(
    {"public", "internal", "confidential", "restricted"}
)


@dataclass(frozen=True)
class SourceLabelPolicy:
    allowed_labels: frozenset[SecurityLabel] = DEFAULT_ALLOWED_LABELS

    def is_allowed(self, evidence_span: EvidenceSpan) -> bool:
        return evidence_span.security_label in self.allowed_labels

    def filter_spans(self, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
        return [span for span in spans if self.is_allowed(span)]

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import get_args

from nornikel_kg.domain.models import EvidenceSpan, SecurityLabel

DEFAULT_ALLOWED_LABELS: frozenset[SecurityLabel] = frozenset(
    {"public", "internal", "confidential", "restricted"}
)
VALID_SECURITY_LABELS: frozenset[SecurityLabel] = frozenset(get_args(SecurityLabel))


def coerce_source_label(raw: str | None) -> SecurityLabel:
    """Resolve a source's label: an explicit valid label, else the
    DEFAULT_SOURCE_LABEL env default ("internal"). Fails closed on an unknown
    value rather than silently defaulting a sensitive source to visible."""
    candidate = (raw or os.getenv("DEFAULT_SOURCE_LABEL") or "internal").strip().lower()
    if candidate not in VALID_SECURITY_LABELS:
        raise ValueError(f"Unknown security label: {candidate!r}")
    return candidate


@dataclass(frozen=True)
class SourceLabelPolicy:
    allowed_labels: frozenset[SecurityLabel] = DEFAULT_ALLOWED_LABELS

    def is_allowed(self, evidence_span: EvidenceSpan) -> bool:
        return evidence_span.security_label in self.allowed_labels

    def filter_spans(self, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
        return [span for span in spans if self.is_allowed(span)]

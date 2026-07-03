from __future__ import annotations

from typing import Protocol

from nornikel_kg.domain.ledger import EvidenceLedgerPacket
from nornikel_kg.domain.models import EvidenceSpan, SourceIngestResponse, SourceSummary


class EvidenceLedgerPort(Protocol):
    def load_demo_packet(self) -> EvidenceLedgerPacket:
        """Return the currently indexed evidence packet."""

    def list_sources(self) -> list[SourceSummary]:
        """Return registered source summaries."""

    def get_source(self, source_id: str) -> SourceSummary | None:
        """Return a source summary by identifier, or None when absent."""

    def list_evidence_spans(self, source_id: str | None = None) -> list[EvidenceSpan]:
        """Return evidence spans, optionally scoped to one source."""

    def delete_source(self, source_id: str) -> bool:
        """Delete one source and all related records. Returns False if source is absent."""

    def ingest_source_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None = None,
    ) -> SourceIngestResponse:
        """Register a CSV or Markdown-like source and extract first-class evidence."""

from __future__ import annotations

import logging
import os
from typing import Protocol

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.qdrant_index.index import EmbeddingDimMismatch
from nornikel_kg.ports.retrieval import IndexableUnit, VectorIndexPort

logger = logging.getLogger(__name__)

EVIDENCE_COLLECTION = os.getenv("QDRANT_COLLECTION", "evidence_units")
# Entity vectors must live in a collection matching the active embedder's
# dimensionality — deriving the name from the evidence collection means an
# embedder switch (new QDRANT_COLLECTION) never queries stale-dim vectors.
ENTITY_COLLECTION = os.getenv("QDRANT_ENTITY_COLLECTION", f"{EVIDENCE_COLLECTION}_entities")


class RerankerPort(Protocol):
    def rerank(
        self, query: str, candidates: list[tuple[str, str]], *, top_k: int
    ) -> list[str]:
        """(unit_id, text) candidates -> unit_ids of the top_k most relevant."""
        ...


class RetrievalService:
    """Qdrant hybrid retrieval over evidence spans, rejoined to DuckDB.

    Retrieval is additive: the deterministic slot-SQL path stays primary and
    any index failure degrades to an empty candidate list, never an error.
    With a reranker attached, hybrid search over-fetches candidates and a
    cross-encoder picks the final top-k (the highest-precision stage).
    """

    def __init__(
        self,
        repository: DuckDBLedgerRepository,
        index: VectorIndexPort | None,
        *,
        reranker: RerankerPort | None = None,
        rerank_candidates: int = 30,
    ) -> None:
        self.repository = repository
        self.index = index
        self.reranker = reranker
        self.rerank_candidates = rerank_candidates

    @property
    def enabled(self) -> bool:
        return self.index is not None

    def index_source(self, source_id: str, *, include_entities: bool = False) -> int:
        """Index one source's spans; entity re-embedding is opt-in.

        Per-source enrichment must NOT re-embed the whole entities collection
        (that quadratic pattern once stalled the stand for hours);
        `reindex_all` refreshes entities once at the end instead.
        """
        if self.index is None:
            return 0
        spans = self.repository.list_evidence_spans(source_id)
        source = self.repository.get_source(source_id)
        # Source title as embedded context: short spans («245 HV | 8 h») are
        # unfindable without the document topic; provenance stays span-exact.
        title_prefix = f"{source.title}\n" if source is not None and source.title else ""
        units = [
            IndexableUnit(
                unit_id=span.span_id,
                text=f"{title_prefix}{span.visible_text}",
                payload={
                    "source_id": span.source_id,
                    "span_type": span.span_type,
                    "security_label": span.security_label,
                },
            )
            for span in spans
            if span.visible_text.strip()
        ]
        try:
            # Incremental: unchanged spans are hash-skipped inside index_units
            # (never deleted first — a failed re-embed must not lose vectors);
            # stale points from a re-parse are pruned afterwards.
            count = self.index.index_units(EVIDENCE_COLLECTION, units)
            prune = getattr(self.index, "prune_source_units", None)
            if prune is not None:
                prune(
                    EVIDENCE_COLLECTION,
                    source_id,
                    {unit.unit_id for unit in units},
                )
            if include_entities:
                count += self._index_entities()
            return count
        except EmbeddingDimMismatch:
            # Deployment/config error (wrong QDRANT_COLLECTION for the backend) —
            # fail loud rather than silently commit an unindexed source.
            raise
        except Exception:
            logger.warning("Indexing failed for %s; retrieval degraded", source_id, exc_info=True)
            return 0

    def reindex_all(self) -> int:
        if self.index is None:
            return 0
        total = 0
        for source in self.repository.list_sources():
            # Entities are global; index them once at the end, not per source.
            total += self.index_source(source.source_id, include_entities=False)
        try:
            total += self._index_entities()
        except Exception:
            logger.warning("Entity indexing failed; resolution fallback degraded", exc_info=True)
        # Ops marker: deploy tooling greps for this exact line to know the
        # rebuild finished (points-count heuristics fire false positives).
        logger.info("Reindex complete: %d units", total)
        return total

    def _index_entities(self) -> int:
        assert self.index is not None
        units = [
            IndexableUnit(
                unit_id=entity["entity_id"],
                text=entity["canonical_name"],
                payload={"entity_type": entity["entity_type"]},
            )
            for entity in self.repository.list_graph_entities()
        ]
        return self.index.index_units(ENTITY_COLLECTION, units)

    def retrieve_span_ids(
        self,
        *,
        question: str,
        allowed_labels: list[str],
        source_ids: list[str] | None = None,
        top_k: int = 15,
    ) -> list[str]:
        """Hybrid search (+ optional rerank) -> span IDs verified in DuckDB."""
        if self.index is None:
            return []
        candidate_k = self.rerank_candidates if self.reranker is not None else top_k
        try:
            hits = self.index.hybrid_search(
                EVIDENCE_COLLECTION,
                query=question,
                top_k=max(candidate_k, top_k),
                allowed_labels=allowed_labels,
                source_ids=source_ids,
            )
        except Exception:
            logger.warning("Hybrid retrieval failed; degrading to SQL-only", exc_info=True)
            return []
        if not hits:
            return []
        # DuckDB rejoin + allowed-label recheck: the index is never authoritative.
        known = {
            span.span_id: span
            for span in self.repository.list_evidence_spans_by_ids(
                [hit.unit_id for hit in hits]
            )
            if span.security_label in allowed_labels
        }
        verified = [hit.unit_id for hit in hits if hit.unit_id in known]
        if self.reranker is None or len(verified) <= top_k:
            return verified[:top_k]
        try:
            reranked = self.reranker.rerank(
                question,
                [(span_id, known[span_id].visible_text) for span_id in verified],
                top_k=top_k,
            )
            filtered = [span_id for span_id in reranked if span_id in known]
            return filtered or verified[:top_k]
        except Exception:
            logger.warning("Reranking failed; returning fused order", exc_info=True)
            return verified[:top_k]

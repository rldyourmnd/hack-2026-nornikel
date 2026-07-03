from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.domain.ids import stable_hash
from nornikel_kg.domain.normalization import canonical_key

logger = logging.getLogger(__name__)

# Production-reference thresholds (plans/09: neo4j-graphrag defaults to 0.8,
# graphiti uses 0.6 + LLM adjudication; we stay conservative).
AUTO_MERGE_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.80

_DIGIT_RE = re.compile(r"\d")


class SemanticMatcherPort(Protocol):
    def match(self, name: str, entity_type: str) -> tuple[str, float] | None:
        """Best (entity_id, cosine score) for a name within one entity type."""


@dataclass(frozen=True)
class ResolutionResult:
    entity_id: str
    action: str  # "matched_key" | "matched_alias" | "matched_semantic" | "created"


class EntityResolutionService:
    """Resolution ladder: exact canonical key -> alias -> semantic -> create.

    The semantic stage (cosine >= 0.90 against the Qdrant `entities`
    collection) merges synonym/translation mentions («электроэкстракция» ≈
    «electrowinning») and writes the mention back as a learned alias, so the
    next resolution is an exact alias hit.

    Guards: mentions carrying digits (alloy codes, formulas — Ni-30Cu vs
    Ni-20Cu often exceed 0.9 cosine) and short strings never merge
    semantically; resolution never crosses entity types. Scores in
    [0.80, 0.90) are logged for audit, not merged.
    """

    def __init__(
        self,
        repository: DuckDBLedgerRepository,
        *,
        semantic_matcher: SemanticMatcherPort | None = None,
    ) -> None:
        self.repository = repository
        self.semantic_matcher = semantic_matcher

    def resolve_or_create(
        self,
        *,
        mention: str,
        entity_type: str,
        span_ids: list[str],
        confidence: float = 0.85,
        metadata: dict[str, object] | None = None,
    ) -> ResolutionResult:
        mention = mention.strip()
        if not mention:
            raise ValueError("Cannot resolve an empty mention")

        existing = self.repository.find_entity(mention, entity_type)
        if existing is not None:
            is_key_match = existing["canonical_key"] == canonical_key(mention)
            self.repository.merge_entity_evidence(
                existing["entity_id"],
                span_ids=span_ids,
                new_alias=None if is_key_match else mention,
            )
            return ResolutionResult(
                entity_id=existing["entity_id"],
                action="matched_key" if is_key_match else "matched_alias",
            )

        semantic_id = self._semantic_match(mention, entity_type)
        if semantic_id is not None:
            self.repository.merge_entity_evidence(
                semantic_id, span_ids=span_ids, new_alias=mention
            )
            return ResolutionResult(entity_id=semantic_id, action="matched_semantic")

        entity_id = f"ent_{entity_type}_{stable_hash([entity_type, canonical_key(mention)], 16)}"
        self.repository.create_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_name=mention,
            evidence_span_ids=span_ids,
            confidence=confidence,
            metadata=dict(metadata) if metadata else None,
        )
        return ResolutionResult(entity_id=entity_id, action="created")

    def _semantic_match(self, mention: str, entity_type: str) -> str | None:
        if self.semantic_matcher is None:
            return None
        key = canonical_key(mention)
        # Digit veto: compositional codes must match exactly, never by cosine.
        if len(key) < 4 or _DIGIT_RE.search(key):
            return None
        try:
            hit = self.semantic_matcher.match(mention, entity_type)
        except Exception:  # semantic stage is additive, never blocks resolution
            logger.warning("Semantic entity match failed for %r", mention, exc_info=True)
            return None
        if hit is None:
            return None
        entity_id, score = hit
        if score >= AUTO_MERGE_THRESHOLD:
            logger.info(
                "Semantic merge: %r -> %s (score %.3f, type %s)",
                mention,
                entity_id,
                score,
                entity_type,
            )
            return entity_id
        if score >= REVIEW_THRESHOLD:
            logger.info(
                "Semantic near-miss (review zone): %r ~ %s (score %.3f, type %s)",
                mention,
                entity_id,
                score,
                entity_type,
            )
        return None


class QdrantSemanticMatcher:
    """Cosine matcher over the `entities` collection (dense-only scores)."""

    def __init__(self, index: object) -> None:
        self._index = index

    def match(self, name: str, entity_type: str) -> tuple[str, float] | None:
        from nornikel_kg.services.retrieval_service import ENTITY_COLLECTION

        dense_search = getattr(self._index, "dense_search", None)
        if dense_search is None:
            return None
        hits = dense_search(
            ENTITY_COLLECTION,
            query=name,
            top_k=1,
            payload_filters={"entity_type": [entity_type]},
        )
        if not hits:
            return None
        return str(hits[0].unit_id), float(hits[0].score)

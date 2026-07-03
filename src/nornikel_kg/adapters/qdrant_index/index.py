from __future__ import annotations

import logging
import uuid
from typing import Any

from nornikel_kg.ports.retrieval import (
    EmbeddingBackendPort,
    IndexableUnit,
    RetrievalHit,
)

logger = logging.getLogger(__name__)

_DENSE_NAME = "dense"
_SPARSE_NAME = "sparse"
# One giant upsert of ~1700 x 1536-float points serializes past Qdrant's
# request-size limit (400 Bad Request observed live) — batch instead.
_UPSERT_BATCH = 128


def _point_id(unit_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, unit_id))


def _text_hash(text: str) -> str:
    import hashlib

    return hashlib.blake2s(text.encode("utf-8"), digest_size=16).hexdigest()


class QdrantVectorIndex:
    """Hybrid dense+sparse index over Qdrant with RRF fusion."""

    def __init__(self, url: str, embeddings: EmbeddingBackendPort) -> None:
        self.url = url
        self.embeddings = embeddings

    def _client(self) -> Any:
        from qdrant_client import QdrantClient

        return QdrantClient(url=self.url, timeout=20)

    def _ensure_collection(self, client: Any, collection: str, dense_dim: int) -> None:
        from qdrant_client import models

        if client.collection_exists(collection):
            return
        client.create_collection(
            collection_name=collection,
            vectors_config={
                _DENSE_NAME: models.VectorParams(
                    size=dense_dim, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                _SPARSE_NAME: models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )

    def index_units(
        self,
        collection: str,
        units: list[IndexableUnit],
        *,
        skip_unchanged: bool = True,
    ) -> int:
        """Incremental upsert: unchanged texts never hit the embedding API.

        Each point carries a `text_hash` payload; units whose stored hash
        matches are skipped entirely. Against a 10 RPS embedding quota this
        turns repeated reindex/enrichment passes from ~30 minutes into
        seconds (the quota is the dominant cost, not Qdrant).
        """
        if not units:
            return 0
        from qdrant_client import models

        client = self._client()
        pending = units
        if skip_unchanged and client.collection_exists(collection):
            existing_hashes: dict[str, str] = {}
            ids = [_point_id(unit.unit_id) for unit in units]
            for start in range(0, len(ids), 512):
                for record in client.retrieve(
                    collection_name=collection,
                    ids=ids[start : start + 512],
                    with_payload=["unit_id", "text_hash"],
                    with_vectors=False,
                ):
                    payload = record.payload or {}
                    existing_hashes[str(payload.get("unit_id", ""))] = str(
                        payload.get("text_hash", "")
                    )
            pending = [
                unit
                for unit in units
                if existing_hashes.get(unit.unit_id) != _text_hash(unit.text)
            ]
            if not pending:
                return 0

        texts = [unit.text for unit in pending]
        dense = self.embeddings.embed_dense(texts)
        sparse = self.embeddings.embed_sparse(texts)
        self._ensure_collection(client, collection, dense_dim=len(dense[0]))
        points = []
        for unit, dense_vector, sparse_vector in zip(pending, dense, sparse, strict=True):
            points.append(
                models.PointStruct(
                    id=_point_id(unit.unit_id),
                    vector={
                        _DENSE_NAME: dense_vector,
                        _SPARSE_NAME: models.SparseVector(
                            indices=sparse_vector.indices, values=sparse_vector.values
                        ),
                    },
                    payload={
                        "unit_id": unit.unit_id,
                        "text": unit.text,
                        "text_hash": _text_hash(unit.text),
                        **unit.payload,
                    },
                )
            )
        for start in range(0, len(points), _UPSERT_BATCH):
            client.upsert(
                collection_name=collection,
                points=points[start : start + _UPSERT_BATCH],
            )
        return len(points)

    def hybrid_search(
        self,
        collection: str,
        *,
        query: str,
        top_k: int = 10,
        allowed_labels: list[str] | None = None,
        source_ids: list[str] | None = None,
    ) -> list[RetrievalHit]:
        from qdrant_client import models

        client = self._client()
        if not client.collection_exists(collection):
            return []
        # Query-side models may differ from document models (Yandex doc/query).
        dense = self.embeddings.embed_dense_query([query])[0]
        # BM25 contract: query vectors carry flat weights, never doc weights.
        sparse = self.embeddings.embed_sparse_query([query])[0]

        conditions: list[Any] = []
        if allowed_labels:
            conditions.append(
                models.FieldCondition(
                    key="security_label", match=models.MatchAny(any=allowed_labels)
                )
            )
        if source_ids:
            conditions.append(
                models.FieldCondition(key="source_id", match=models.MatchAny(any=source_ids))
            )
        query_filter = models.Filter(must=conditions) if conditions else None

        # Fusion needs a candidate pool well above the final limit; filters go
        # into every prefetch too (version-stable propagation).
        prefetch_limit = max(50, top_k * 3)
        prefetch = [
            models.Prefetch(
                query=dense, using=_DENSE_NAME, limit=prefetch_limit, filter=query_filter
            ),
        ]
        if sparse.indices:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(indices=sparse.indices, values=sparse.values),
                    using=_SPARSE_NAME,
                    limit=prefetch_limit,
                    filter=query_filter,
                )
            )
        response = client.query_points(
            collection_name=collection,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [
            RetrievalHit(
                unit_id=str((point.payload or {}).get("unit_id", point.id)),
                score=float(point.score),
                payload=dict(point.payload or {}),
            )
            for point in response.points
        ]

    def dense_search(
        self,
        collection: str,
        *,
        query: str,
        top_k: int = 5,
        payload_filters: dict[str, list[str]] | None = None,
    ) -> list[RetrievalHit]:
        """Dense-only search returning raw cosine scores (for thresholding)."""
        from qdrant_client import models

        client = self._client()
        if not client.collection_exists(collection):
            return []
        dense = self.embeddings.embed_dense_query([query])[0]
        conditions: list[Any] = [
            models.FieldCondition(key=key, match=models.MatchAny(any=values))
            for key, values in (payload_filters or {}).items()
            if values
        ]
        response = client.query_points(
            collection_name=collection,
            query=dense,
            using=_DENSE_NAME,
            query_filter=models.Filter(must=conditions) if conditions else None,
            limit=top_k,
            with_payload=True,
        )
        return [
            RetrievalHit(
                unit_id=str((point.payload or {}).get("unit_id", point.id)),
                score=float(point.score),
                payload=dict(point.payload or {}),
            )
            for point in response.points
        ]

    def prune_source_units(
        self, collection: str, source_id: str, keep_unit_ids: set[str]
    ) -> int:
        """Remove a source's stale points (re-parse produced new span ids)."""
        from qdrant_client import models

        client = self._client()
        if not client.collection_exists(collection):
            return 0
        stale: list[int | str | uuid.UUID] = []
        offset = None
        while True:
            records, offset = client.scroll(
                collection_name=collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id", match=models.MatchValue(value=source_id)
                        )
                    ]
                ),
                with_payload=["unit_id"],
                with_vectors=False,
                limit=1024,
                offset=offset,
            )
            for record in records:
                unit_id = str((record.payload or {}).get("unit_id", ""))
                if unit_id and unit_id not in keep_unit_ids:
                    stale.append(str(record.id))
            if offset is None:
                break
        if stale:
            client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=stale),
            )
        return len(stale)

    def delete_source_units(self, collection: str, source_id: str) -> None:
        from qdrant_client import models

        client = self._client()
        if not client.collection_exists(collection):
            return
        client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_id", match=models.MatchValue(value=source_id)
                        )
                    ]
                )
            ),
        )

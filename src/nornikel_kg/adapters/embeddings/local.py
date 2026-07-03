from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from nornikel_kg.ports.retrieval import SparseVector

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _dense_model() -> Any:
    from sentence_transformers import SentenceTransformer

    model_id = os.getenv("EMBEDDING_MODEL_ID", "deepvk/USER-bge-m3")
    logger.info("Loading dense embedding model %s", model_id)
    return SentenceTransformer(model_id, device="cpu")


@lru_cache(maxsize=1)
def _sparse_model() -> Any:
    from fastembed import SparseTextEmbedding

    model_id = os.getenv("SPARSE_MODEL_ID", "Qdrant/bm25")
    # fastembed's Bm25 defaults to language="english" (Snowball stemmer +
    # stopwords) — on a Russian corpus that silently breaks the sparse leg of
    # hybrid search for exact terms («сульфат», «электроэкстракция»).
    language = os.getenv("SPARSE_LANGUAGE", "russian")
    logger.info("Loading sparse embedding model %s (language=%s)", model_id, language)
    return SparseTextEmbedding(model_name=model_id, language=language)


def _to_sparse(embedding: Any) -> SparseVector:
    return SparseVector(
        indices=[int(i) for i in embedding.indices],
        values=[float(v) for v in embedding.values],
    )


class LocalEmbeddingBackend:
    """CPU embeddings: USER-bge-m3 dense + fastembed BM25 sparse."""

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        vectors = _dense_model().encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_dense_query(self, texts: list[str]) -> list[list[float]]:
        # USER-bge-m3 is symmetric: queries and documents share one model.
        return self.embed_dense(texts)

    def embed_sparse(self, texts: list[str]) -> list[SparseVector]:
        return [_to_sparse(embedding) for embedding in _sparse_model().embed(texts)]

    def embed_sparse_query(self, texts: list[str]) -> list[SparseVector]:
        # BM25 queries must not carry document term weights (fastembed
        # contract: query terms get weight 1.0; IDF happens in Qdrant).
        return [_to_sparse(embedding) for embedding in _sparse_model().query_embed(texts)]

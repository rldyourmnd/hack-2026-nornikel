from __future__ import annotations

import hashlib
import math

from nornikel_kg.ports.retrieval import SparseVector

_DIM = 64


class FakeEmbeddingBackend:
    """Deterministic hash-based embeddings for CI and offline tests.

    Texts sharing tokens land near each other because each token contributes
    the same pseudo-random direction; no model download, no randomness.
    """

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_dense_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed_dense(texts)

    def embed_sparse(self, texts: list[str]) -> list[SparseVector]:
        vectors: list[SparseVector] = []
        for text in texts:
            weights: dict[int, float] = {}
            for token in text.lower().split():
                index = int.from_bytes(
                    hashlib.blake2s(token.encode("utf-8"), digest_size=4).digest(), "big"
                )
                weights[index] = weights.get(index, 0.0) + 1.0
            vectors.append(
                SparseVector(indices=sorted(weights), values=[weights[i] for i in sorted(weights)])
            )
        return vectors

    def embed_sparse_query(self, texts: list[str]) -> list[SparseVector]:
        # Query vectors mirror document vectors with flat weights (BM25 contract).
        return [
            SparseVector(indices=vector.indices, values=[1.0] * len(vector.indices))
            for vector in self.embed_sparse(texts)
        ]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * _DIM
        for token in text.lower().split():
            digest = hashlib.blake2s(token.encode("utf-8"), digest_size=_DIM).digest()
            for position, byte in enumerate(digest):
                vector[position] += (byte - 127.5) / 127.5
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

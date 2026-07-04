from __future__ import annotations

import logging
import os
import random
import time

from nornikel_kg.adapters.ratelimit import get_limiter
from nornikel_kg.ports.retrieval import SparseVector

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_TIMEOUT_S = 60.0
# The OpenAI /embeddings API returns one vector per input in a single call, so
# batching offloads the whole per-doc span set in a few requests — the fix for
# CPU-bound local dense embedding on a constrained stand. dataeyes caps a batch
# at ~32 inputs (larger returns 403), so keep the default conservative.
_MAX_BATCH = int(os.getenv("EMBEDDING_BATCH", "32"))
_MAX_INPUT_CHARS = 8000


class OpenAIEmbeddingBackend:
    """Dense embeddings via an OpenAI-compatible ``/embeddings`` endpoint (e.g.
    dataeyes); sparse BM25 stays local (fastembed, same as the local backend).

    Dense vectors are produced by the provider API in batched requests, which
    keeps the 8-vCPU stand free for Docling parsing during bulk ingest.
    """

    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        base = api_base or os.getenv("EMBEDDING_API_BASE") or os.getenv("DATAEYES_API_BASE") or ""
        self.api_base = base.rstrip("/")
        self.api_key = (
            api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("DATAEYES_API_KEY") or ""
        )
        self.model = model or os.getenv("EMBEDDING_MODEL_ID", "text-embedding-3-small")
        if not self.api_base or not self.api_key:
            raise ValueError(
                "OpenAIEmbeddingBackend needs EMBEDDING_API_BASE/EMBEDDING_API_KEY "
                "(or DATAEYES_API_BASE/DATAEYES_API_KEY)"
            )

    # -- dense (API, batched) ----------------------------------------------
    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            batch = [text[:_MAX_INPUT_CHARS] for text in texts[start : start + _MAX_BATCH]]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def embed_dense_query(self, texts: list[str]) -> list[list[float]]:
        return self.embed_dense(texts)

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        import httpx

        limiter = get_limiter("openai-embeddings", float(os.getenv("EMBEDDING_RPS", "8")))
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                limiter.acquire()
                response = httpx.post(
                    f"{self.api_base}/embeddings",
                    json={"model": self.model, "input": batch},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=_TIMEOUT_S,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
                response.raise_for_status()
                data = response.json()["data"]
                # Preserve input order — the API returns each item with its index.
                ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
                return [[float(v) for v in item["embedding"]] for item in ordered]
            except Exception as error:  # noqa: BLE001 - bounded retry loop
                last_error = error
                if attempt == _MAX_RETRIES:
                    break
                logger.warning(
                    "OpenAI embedding attempt %s failed (%s); retrying in %.1fs",
                    attempt,
                    str(error)[:100],
                    delay,
                )
                time.sleep(delay + random.uniform(0, delay / 2))
                delay = min(delay * 2, 20.0)
        raise RuntimeError(
            f"OpenAI embedding failed after {_MAX_RETRIES} attempts"
        ) from last_error

    # -- sparse (local fastembed BM25, same as LocalEmbeddingBackend) -------
    def embed_sparse(self, texts: list[str]) -> list[SparseVector]:
        from nornikel_kg.adapters.embeddings.local import LocalEmbeddingBackend

        return LocalEmbeddingBackend().embed_sparse(texts)

    def embed_sparse_query(self, texts: list[str]) -> list[SparseVector]:
        from nornikel_kg.adapters.embeddings.local import LocalEmbeddingBackend

        return LocalEmbeddingBackend().embed_sparse_query(texts)

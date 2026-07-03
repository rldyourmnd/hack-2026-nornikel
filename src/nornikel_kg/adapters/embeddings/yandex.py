from __future__ import annotations

import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from nornikel_kg.ports.retrieval import SparseVector

logger = logging.getLogger(__name__)


class _RateLimiter:
    """Process-wide min-interval limiter for the shared folder quota.

    Retry-with-backoff alone loses against a saturated 10 RPS quota (all
    attempts land in 429 when many threads fire concurrently — observed
    live); pacing requests below the quota at the source is the fix.
    """

    def __init__(self, requests_per_second: float) -> None:
        self._interval = 1.0 / max(requests_per_second, 0.1)
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(self._next_slot, now) + self._interval
        if wait > 0:
            time.sleep(wait)


_rate_limiter = _RateLimiter(float(os.getenv("YANDEX_EMBED_RPS", "8")))

# Canonical AI Studio host (docs, 2026-06): ai.api.cloud.yandex.net; the old
# llm.api host still answers but is the legacy alias.
_API_URL = "https://ai.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
# The new-generation unified embedder (1536-dim, newer than the documented
# text-embeddings-v2 pair) serves both documents and queries; the split pairs
# (text-embeddings-v2-doc/-query, text-search-doc/-query) stay available
# through the env overrides.
_DEFAULT_MODEL = "text-embeddings/latest"
_MAX_RETRIES = 7
_TIMEOUT_S = 30.0
# Documented input cap is 2048 tokens (v1 wording; compat ref says 8192).
# Russian text ≈ 2-3 chars/token on the Yandex tokenizer — 4000 chars stays
# safely under the stricter bound, and a 400 here would sink the whole
# source's indexing pass.
_MAX_INPUT_CHARS = 4000


class YandexEmbeddingBackend:
    """Dense embeddings via Yandex AI Studio; sparse BM25 stays local.

    Dense vectors come from the organizers' Yandex AI Studio API (offloads
    the 8-vCPU stand from torch inference); BM25 sparse vectors are produced
    by fastembed exactly as in the local backend, so hybrid search keeps its
    lexical leg offline.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        folder_id: str | None = None,
        doc_model: str | None = None,
        query_model: str | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.api_key: str = api_key if api_key else os.getenv("YANDEX_API_KEY", "")
        self.folder_id: str = folder_id if folder_id else os.getenv("YANDEX_FOLDER_ID", "")
        if not self.api_key or not self.folder_id:
            raise ValueError("YandexEmbeddingBackend needs YANDEX_API_KEY and YANDEX_FOLDER_ID")
        doc = doc_model or os.getenv("YANDEX_EMBED_DOC_MODEL", _DEFAULT_MODEL)
        query = query_model or os.getenv("YANDEX_EMBED_QUERY_MODEL", _DEFAULT_MODEL)
        self.doc_model_uri = f"emb://{self.folder_id}/{doc}"
        self.query_model_uri = f"emb://{self.folder_id}/{query}"
        # The folder quota (10 RPS) is shared across ALL callers — concurrent
        # enrichment threads each spinning 8 workers produced a 429 storm.
        self.max_workers = max_workers or int(os.getenv("YANDEX_EMBED_MAX_WORKERS", "4"))

    # -- dense (API) --------------------------------------------------------

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        return self._embed_many(texts, self.doc_model_uri)

    # Repeated demo questions re-embed the same query strings; a small
    # process-wide cache spares both latency and the shared RPS quota.
    _query_cache: dict[tuple[str, str], list[float]] = {}
    _query_cache_lock = threading.Lock()
    _QUERY_CACHE_MAX = 256

    def embed_dense_query(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float] | None] = []
        missing: list[str] = []
        with self._query_cache_lock:
            for text in texts:
                cached = self._query_cache.get((self.query_model_uri, text))
                results.append(list(cached) if cached is not None else None)
                if cached is None:
                    missing.append(text)
        if missing:
            fresh = self._embed_many(missing, self.query_model_uri)
            with self._query_cache_lock:
                for text, vector in zip(missing, fresh, strict=True):
                    if len(self._query_cache) >= self._QUERY_CACHE_MAX:
                        self._query_cache.pop(next(iter(self._query_cache)))
                    self._query_cache[(self.query_model_uri, text)] = vector
            fresh_iter = iter(fresh)
            results = [
                vector if vector is not None else list(next(fresh_iter))
                for vector in results
            ]
        return [vector for vector in results if vector is not None]

    def _embed_many(self, texts: list[str], model_uri: str) -> list[list[float]]:
        if not texts:
            return []
        if len(texts) == 1:
            return [self._embed_one(texts[0], model_uri)]
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(lambda text: self._embed_one(text, model_uri), texts))

    def _embed_one(self, text: str, model_uri: str) -> list[float]:
        import httpx

        payload = {"modelUri": model_uri, "text": text[:_MAX_INPUT_CHARS]}
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                _rate_limiter.acquire()
                response = httpx.post(
                    _API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Api-Key {self.api_key}",
                        "x-folder-id": self.folder_id,
                    },
                    timeout=_TIMEOUT_S,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
                response.raise_for_status()
                return [float(v) for v in response.json()["embedding"]]
            except Exception as error:  # noqa: BLE001 - bounded retry loop
                last_error = error
                if attempt == _MAX_RETRIES:
                    break
                logger.warning(
                    "Yandex embedding attempt %s failed (%s); retrying in %.1fs",
                    attempt,
                    str(error)[:100],
                    delay,
                )
                # Jitter prevents retry stampedes across concurrent workers.
                time.sleep(delay + random.uniform(0, delay / 2))
                delay = min(delay * 2, 20.0)
        raise RuntimeError(f"Yandex embedding failed after {_MAX_RETRIES} attempts") from last_error

    # -- sparse (local fastembed, same as LocalEmbeddingBackend) ------------

    def embed_sparse(self, texts: list[str]) -> list[SparseVector]:
        from nornikel_kg.adapters.embeddings.local import LocalEmbeddingBackend

        return LocalEmbeddingBackend().embed_sparse(texts)

    def embed_sparse_query(self, texts: list[str]) -> list[SparseVector]:
        from nornikel_kg.adapters.embeddings.local import LocalEmbeddingBackend

        return LocalEmbeddingBackend().embed_sparse_query(texts)

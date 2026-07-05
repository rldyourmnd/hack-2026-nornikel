from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# The default neural reranker must stay CPU-feasible. The previous
# BAAI/bge-reranker-v2-m3 default was multilingual but too slow on the stand
# CPU and triggered per-request ONNX export. Use the neural reranker only as an
# explicit opt-in; the runtime default is the model-free LexicalReranker.
_DEFAULT_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model() -> Any:
    from sentence_transformers import CrossEncoder

    model_id = os.getenv("RERANKER_MODEL_ID", _DEFAULT_MODEL_ID)
    backend = os.getenv("RERANKER_BACKEND", "torch")
    device = os.getenv("RERANKER_DEVICE", "cpu")
    logger.info("Loading reranker %s (backend=%s)", model_id, backend)
    try:
        return CrossEncoder(model_id, backend=backend, device=device)
    except Exception:
        if backend == "torch":
            raise
        logger.warning("Reranker backend %s unavailable; falling back to torch", backend)
        return CrossEncoder(model_id, backend="torch", device=device)


class CrossEncoderReranker:
    """Query-document relevance reranking on CPU.

    Applied to the hybrid-retrieval candidate pool (top-30) to pick the final
    top-k; the single most reliable component-level precision boost for RAG.
    """

    max_chars = int(os.getenv("RERANKER_MAX_CHARS", "512"))
    batch_size = int(os.getenv("RERANKER_BATCH_SIZE", "8"))

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str]],
        *,
        top_k: int,
    ) -> list[str]:
        """(unit_id, text) candidates -> unit_ids of the top_k most relevant."""
        if not candidates:
            return []
        if len(candidates) <= top_k:
            ordered = candidates
        else:
            model = _load_model()
            pairs = [(query, text[: self.max_chars]) for _, text in candidates]
            scores = model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)
            ranked = sorted(
                zip(candidates, scores, strict=True), key=lambda item: -float(item[1])
            )
            ordered = [candidate for candidate, _ in ranked]
        return [unit_id for unit_id, _ in ordered[:top_k]]

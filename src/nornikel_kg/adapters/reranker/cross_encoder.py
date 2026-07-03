from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# BAAI/bge-reranker-v2-m3: Apache-2.0, multilingual (XLM-R backbone, RU
# covered via MIRACL training). ONNX backend when optimum is present, torch
# fallback otherwise. Evidence: plans/09 (SOTA research, 2026-07-03).
_DEFAULT_MODEL_ID = "BAAI/bge-reranker-v2-m3"


@lru_cache(maxsize=1)
def _load_model() -> Any:
    from sentence_transformers import CrossEncoder

    model_id = os.getenv("RERANKER_MODEL_ID", _DEFAULT_MODEL_ID)
    backend = os.getenv("RERANKER_BACKEND", "onnx")
    logger.info("Loading reranker %s (backend=%s)", model_id, backend)
    try:
        return CrossEncoder(model_id, backend=backend, device="cpu")
    except Exception:
        if backend == "torch":
            raise
        logger.warning("Reranker backend %s unavailable; falling back to torch", backend)
        return CrossEncoder(model_id, backend="torch", device="cpu")


class CrossEncoderReranker:
    """Query-document relevance reranking on CPU.

    Applied to the hybrid-retrieval candidate pool (top-30) to pick the final
    top-k; the single most reliable component-level precision boost for RAG.
    """

    max_chars = 1600  # ~512 tokens; cross-encoder input cap

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
            scores = model.predict(pairs)
            ranked = sorted(
                zip(candidates, scores, strict=True), key=lambda item: -float(item[1])
            )
            ordered = [candidate for candidate, _ in ranked]
        return [unit_id for unit_id, _ in ordered[:top_k]]

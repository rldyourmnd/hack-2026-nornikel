from __future__ import annotations

import os

from fastapi import APIRouter

from nornikel_kg import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    llm_enabled = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
    llm_configured = bool(
        os.getenv("LLM_API_BASE") and os.getenv("LLM_API_KEY") and os.getenv("LLM_ANSWER_MODEL")
    )
    return {
        "status": "ok",
        "version": __version__,
        "llm_enabled": llm_enabled,
        "llm_configured": llm_enabled and llm_configured,
        "embedding_backend": os.getenv("EMBEDDING_BACKEND", "off"),
    }

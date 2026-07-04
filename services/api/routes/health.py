from __future__ import annotations

import os

from fastapi import APIRouter

from nornikel_kg import __version__
from nornikel_kg.adapters.llm.settings import LLMSettings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = LLMSettings()
    llm_configured = bool(
        settings.llm_api_base and settings.llm_api_key and settings.llm_answer_model
    )
    return {
        "status": "ok",
        "version": __version__,
        "llm_enabled": settings.llm_enabled,
        "llm_configured": settings.llm_enabled and llm_configured,
        "embedding_backend": os.getenv("EMBEDDING_BACKEND", "off"),
    }

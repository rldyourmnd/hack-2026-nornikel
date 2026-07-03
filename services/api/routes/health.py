from __future__ import annotations

import os

from fastapi import APIRouter

from nornikel_kg import __version__

router = APIRouter(tags=["health"])


def _model_label(env_uri: str) -> str:
    """Human-readable model name from a gpt://<folder>/<model>/latest URI."""
    if not env_uri:
        return "deterministic-fake"
    tail = env_uri.rstrip("/").split("/")
    # …/<model>/latest -> <model>
    return tail[-2] if len(tail) >= 2 and tail[-1] == "latest" else tail[-1]


@router.get("/health")
def health() -> dict[str, object]:
    llm_enabled = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
    return {
        "status": "ok",
        "version": __version__,
        "llm_enabled": llm_enabled,
        "answer_model": _model_label(os.getenv("LLM_ANSWER_MODEL", "")) if llm_enabled else "off",
        "extraction_model": (
            _model_label(os.getenv("LLM_EXTRACTION_MODEL", "")) if llm_enabled else "off"
        ),
        "embedding_backend": os.getenv("EMBEDDING_BACKEND", "off"),
    }

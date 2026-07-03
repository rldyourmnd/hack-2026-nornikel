from __future__ import annotations

from fastapi import APIRouter

from nornikel_kg import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}

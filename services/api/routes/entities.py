from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from nornikel_kg.services.runtime import get_graph_service, get_ledger_repository

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/search")
def search_entities(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, list[dict[str, object]]]:
    results = get_ledger_repository().search_entities(q, limit=limit)
    return {"entities": [dict(item) for item in results]}


@router.get("/{entity_id}")
def get_entity(entity_id: str) -> dict[str, object]:
    entity = get_ledger_repository().get_entity(entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    neighborhood = get_graph_service().neighborhood(entity_id, depth=1, limit=25)
    return {
        "entity": entity,
        "neighborhood": neighborhood,
    }

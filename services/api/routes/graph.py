from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from nornikel_kg.services.runtime import (
    get_graph_service,
    get_ledger_repository,
)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/timeline")
def timeline() -> dict[str, list[dict[str, object]]]:
    """Dated knowledge events: decisions/conclusions plus dated publications.

    Publication entities carry year/date extracted from document heads at
    enrichment time, so the timeline stays populated on real corpora where
    decision entities are scarce.
    """
    repository = get_ledger_repository()
    entities = repository.list_graph_entities()
    events: list[dict[str, object]] = []
    for entity in entities:
        if entity["entity_type"] not in {"decision", "conclusion", "publication"}:
            continue
        card = repository.get_entity(entity["entity_id"])
        if card is None:
            continue
        date = card["metadata"].get("date")
        year = card["metadata"].get("year")
        if entity["entity_type"] == "publication" and date is None and year is None:
            continue  # undated publications add noise, not history
        events.append(
            {
                "entity_id": card["entity_id"],
                "entity_type": card["entity_type"],
                "title": card["canonical_name"],
                "date": date,
                "year": year,
                "evidence_span_ids": card["evidence_span_ids"],
            }
        )
    events.sort(
        key=lambda event: str(event.get("date") or event.get("year") or ""),
        reverse=True,
    )
    return {"events": events}


@router.get("/neighborhood")
def neighborhood(
    entity_id: str = Query(min_length=1),
    depth: int = Query(default=1, ge=1, le=2),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    result = get_graph_service().neighborhood(entity_id, depth=depth, limit=limit)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return result



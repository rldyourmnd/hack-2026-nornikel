from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from nornikel_kg.domain.models import AskRequest
from nornikel_kg.services.runtime import (
    get_graph_service,
    get_ledger_repository,
    get_qa_service,
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


@router.get("/demo-path")
def demo_path() -> dict[str, object]:
    response = get_qa_service().ask(
        AskRequest(question="Что делали по Ni-30Cu при старении 700 C 8 ч?")
    )
    if not response.graph_paths:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No demo path available in the current ledger",
        )
    path = response.graph_paths[0]
    node_types = [
        "Material",
        "Experiment",
        "Regime",
        "Step",
        "Measurement",
        "Property",
        "Evidence",
        "Document",
    ]
    return {
        "nodes": [
            {
                "id": node_id,
                "type": node_types[index] if index < len(node_types) else "Node",
                "label": node_id,
            }
            for index, node_id in enumerate(path.nodes)
        ],
        "edges": [
            {
                "source": path.nodes[index],
                "target": path.nodes[index + 1],
                "label": relationship,
            }
            for index, relationship in enumerate(path.relationships)
        ],
    }

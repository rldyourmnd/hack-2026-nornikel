from __future__ import annotations

from fastapi import APIRouter

from nornikel_kg.domain.analysis import GapAnalyzer
from nornikel_kg.services.runtime import get_ledger_repository

router = APIRouter(prefix="/gaps", tags=["gaps"])


@router.get("/analyze")
def analyze_gaps() -> dict[str, object]:
    repository = get_ledger_repository()
    entities = repository.list_graph_entities()
    # Dictionary-seeded entities only (stable IDs); extracted ent_* stay out of the matrix.
    def dictionary_entities(entity_type: str) -> list[dict[str, object]]:
        return [
            entity
            for entity in entities
            if entity["entity_type"] == entity_type
            and not str(entity["entity_id"]).startswith("ent_")
        ]

    materials = dictionary_entities("material")
    regimes = dictionary_entities("regime")
    properties = dictionary_entities("property")
    packet = repository.load_evidence_packet()
    return GapAnalyzer().coverage(
        materials=materials,
        regimes=regimes,
        properties=properties,
        experiments=packet.experiments,
    )

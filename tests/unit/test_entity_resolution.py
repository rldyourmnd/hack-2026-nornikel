from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.services.entity_resolution import EntityResolutionService


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "resolution.duckdb")
    repo.migrate()
    return repo


@pytest.fixture()
def service(repository: DuckDBLedgerRepository) -> EntityResolutionService:
    return EntityResolutionService(repository)


def test_exact_canonical_key_match_merges_evidence(
    service: EntityResolutionService, repository: DuckDBLedgerRepository
) -> None:
    result = service.resolve_or_create(
        mention="Медный штейн", entity_type="material", span_ids=["evs_a"]
    )
    assert result.action == "matched_key"
    assert result.entity_id == "mat_matte_copper"
    entity = repository.get_entity("mat_matte_copper")
    assert entity is not None and "evs_a" in entity["evidence_span_ids"]


def test_dash_variant_matches_same_entity(service: EntityResolutionService) -> None:
    # hyphen vs en-dash of the same created mention resolve to one entity
    first = service.resolve_or_create(
        mention="Ni-Cu опытный", entity_type="material", span_ids=["evs_b1"]
    )
    second = service.resolve_or_create(
        mention="Ni–Cu опытный", entity_type="material", span_ids=["evs_b2"]
    )
    assert first.entity_id == second.entity_id


def test_alias_match_learns_evidence(
    service: EntityResolutionService, repository: DuckDBLedgerRepository
) -> None:
    result = service.resolve_or_create(
        mention="катодный никель", entity_type="material", span_ids=["evs_c"]
    )
    assert result.action == "matched_alias"
    assert result.entity_id == "mat_nickel_cathode"


def test_unknown_mention_creates_new_entity(
    service: EntityResolutionService, repository: DuckDBLedgerRepository
) -> None:
    result = service.resolve_or_create(
        mention="Ni-20Cu", entity_type="material", span_ids=["evs_d"]
    )
    assert result.action == "created"
    assert result.entity_id != "mat_nicu_30"
    entity = repository.get_entity(result.entity_id)
    assert entity is not None
    assert entity["canonical_name"] == "Ni-20Cu"
    assert entity["validation_status"] == "extracted"


def test_near_duplicate_materials_never_merge(service: EntityResolutionService) -> None:
    first = service.resolve_or_create(
        mention="Ni-30Cu", entity_type="material", span_ids=["evs_e"]
    )
    second = service.resolve_or_create(
        mention="Ni-20Cu", entity_type="material", span_ids=["evs_f"]
    )
    assert first.entity_id != second.entity_id


def test_resolution_does_not_cross_entity_types(service: EntityResolutionService) -> None:
    material = service.resolve_or_create(
        mention="Aging", entity_type="material", span_ids=["evs_g"]
    )
    assert material.action == "created"
    assert material.entity_id != "regime_aging"


def test_repeated_resolution_is_idempotent(
    service: EntityResolutionService, repository: DuckDBLedgerRepository
) -> None:
    first = service.resolve_or_create(
        mention="Custom Alloy X", entity_type="material", span_ids=["evs_h"]
    )
    second = service.resolve_or_create(
        mention="Custom Alloy X", entity_type="material", span_ids=["evs_h", "evs_i"]
    )
    assert first.entity_id == second.entity_id
    entity = repository.get_entity(first.entity_id)
    assert entity is not None
    assert entity["evidence_span_ids"].count("evs_h") == 1

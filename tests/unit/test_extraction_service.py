from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.llm import FakeLLM
from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument
from nornikel_kg.services.extraction_service import ExtractionService


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "extraction.duckdb")
    repo.migrate()
    return repo


def _ingest_text(repository: DuckDBLedgerRepository, source_id: str, lines: list[str]) -> None:
    parsed = ParsedDocument(
        blocks=[
            ParsedBlock(text=line, page=1, locator=f"block_{index}")
            for index, line in enumerate(lines, start=1)
        ],
        tables=[],
        title=source_id,
        parser_profile="test_v1",
    )
    repository.ingest_parsed_document(
        source_id=source_id,
        raw_sha256="0" * 64,
        title=source_id,
        document_type="pdf",
        parsed=parsed,
        artifact_locator=f"{source_id}.pdf",
    )


def test_rule_extraction_links_known_entities(repository: DuckDBLedgerRepository) -> None:
    _ingest_text(
        repository,
        "src_report1",
        ["Медный штейн подвергали конвертированию в печи Ванюкова; извлечение выросло."],
    )
    service = ExtractionService(repository, use_gliner=False)
    counters = service.process_source("src_report1")
    assert counters["entities"] >= 3  # material + regime + equipment
    material = repository.get_entity("mat_matte_copper")
    assert material is not None
    assert len(material["evidence_span_ids"]) >= 1
    relations = repository.list_graph_relations()
    relation_types = {relation["relation_type"] for relation in relations}
    assert "APPLIES_REGIME" in relation_types
    assert all(relation["evidence_span_ids"] for relation in relations)


def test_second_document_auto_links_to_existing_graph(
    repository: DuckDBLedgerRepository,
) -> None:
    service = ExtractionService(repository, use_gliner=False)
    _ingest_text(repository, "src_doc1", ["Медный штейн подвергали плавке при 1200 C."])
    service.process_source("src_doc1")
    material_before = repository.get_entity("mat_matte_copper")
    assert material_before is not None
    spans_before = len(material_before["evidence_span_ids"])

    _ingest_text(
        repository,
        "src_doc2",
        ["Новый протокол: медный штейн переработали, использовалась Печь Ванюкова."],
    )
    service.process_source("src_doc2")
    material_after = repository.get_entity("mat_matte_copper")
    assert material_after is not None
    assert len(material_after["evidence_span_ids"]) > spans_before
    relations = repository.list_graph_relations()
    equipment_edges = [
        relation for relation in relations if relation["relation_type"] == "USED_EQUIPMENT"
    ]
    assert equipment_edges, "second document must add USED_EQUIPMENT edge to existing node"


def test_alias_mention_merges_into_canonical_entity(
    repository: DuckDBLedgerRepository,
) -> None:
    _ingest_text(
        repository,
        "src_alias",
        ["Файнштейн показал рост извлечения при конвертировании."],
    )
    service = ExtractionService(repository, use_gliner=False)
    service.process_source("src_alias")
    entity = repository.get_entity("mat_matte_nickel")
    assert entity is not None
    assert len(entity["evidence_span_ids"]) >= 1


def test_invalid_llm_payload_falls_back_to_rules(repository: DuckDBLedgerRepository) -> None:
    _ingest_text(
        repository,
        "src_llm",
        [
            "Сплав Ni-30Cu подвергался отжигу при температуре 850 градусов "
            "в атмосфере аргона в течение двух часов."
        ],
    )
    fake = FakeLLM(canned={"extraction": {"not": "matching schema"}})
    service = ExtractionService(repository, llm=fake, use_gliner=False)
    counters = service.process_source("src_llm")
    assert counters["entities"] >= 2  # rules still resolve material + regime
    assert len(fake.calls) >= 1


def test_valid_llm_payload_adds_mentions(repository: DuckDBLedgerRepository) -> None:
    _ingest_text(
        repository,
        "src_llm2",
        [
            "Работы по подготовке и аттестации образцов выполняла "
            "лаборатория металлургии в первом квартале года."
        ],
    )
    fake = FakeLLM(
        canned={
            "extraction": {
                "entities": [
                    {"text": "лаборатория металлургии", "entity_type": "laboratory"},
                ],
                "relations": [],
            }
        }
    )
    service = ExtractionService(repository, llm=fake, use_gliner=False)
    service.process_source("src_llm2")
    results = repository.search_entities("лаборатория металлургии")
    assert results, "LLM-extracted laboratory entity must be created"

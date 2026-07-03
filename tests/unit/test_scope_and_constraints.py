from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.domain.models import AskFilters, AskRequest
from nornikel_kg.domain.quantities import NumericConstraint, parse_numeric_constraints
from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument
from nornikel_kg.services.extraction_service import ExtractionService, _extract_authors
from nornikel_kg.services.qa_service import DemoQAService


def test_numeric_constraint_parser_handles_ru_operators() -> None:
    constraints = parse_numeric_constraints(
        "вода содержит сульфаты не более 300 мг/л, а остаток ≤1000 мг/дм³ при не менее 20 %"
    )
    assert NumericConstraint("<=", 300.0, "мг/л") in constraints
    # мг/дм³ is physically the same unit as мг/л and must canonicalize to it.
    assert NumericConstraint("<=", 1000.0, "мг/л") in constraints
    assert NumericConstraint(">=", 20.0, "%") in constraints


def test_author_extraction_ru_and_en() -> None:
    head = (
        "UDC 669 INVESTIGATION ... D.M. Bogatyrev, Researcher, e-mail: b@x.ru "
        "Новожилова О.С., инженер лаборатории. Цымбулов Л.Б., директор."
    )
    authors = _extract_authors(head)
    assert any("Новожилова" in author for author in authors)
    assert any("Bogatyrev" in author for author in authors)


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "scope.duckdb")
    repo.migrate()
    return repo


def test_real_domain_dictionary_resolves(repository: DuckDBLedgerRepository) -> None:
    assert repository.find_entity("шлак", "material") is not None
    assert repository.find_entity("электроэкстракция", "regime") is not None
    assert repository.find_entity("ПВП", "equipment") is not None
    assert repository.find_entity("скорость циркуляции", "property") is not None


def test_publication_and_authors_linked(repository: DuckDBLedgerRepository) -> None:
    parsed = ParsedDocument(
        blocks=[
            ParsedBlock(
                text="Иванов И.И., старший научный сотрудник. Обеднение шлака печи Ванюкова.",
                page=1,
                locator="block_1",
            ),
            ParsedBlock(
                text="Металлическая фаза и потери металлов при плавке изучены детально.",
                page=1,
                locator="block_2",
            ),
        ],
        tables=[],
        title="Отчет об обеднении шлака",
        parser_profile="test_v1",
    )
    repository.ingest_parsed_document(
        source_id="src_pub",
        raw_sha256="0" * 64,
        title="Отчет об обеднении шлака",
        document_type="pdf",
        parsed=parsed,
        artifact_locator="report.pdf",
    )
    ExtractionService(repository, use_gliner=False).process_source("src_pub")
    publications = [
        e for e in repository.list_graph_entities() if e["entity_type"] == "publication"
    ]
    assert publications, "source must become a publication entity"
    relations = repository.list_graph_relations()
    relation_types = {r["relation_type"] for r in relations}
    assert "DESCRIBED_IN" in relation_types
    assert "AUTHORED_BY" in relation_types


def test_geography_and_year_scope_filters(repository: DuckDBLedgerRepository) -> None:
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_scope,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,210,245,HV,increase\n"
    )
    response = repository.ingest_source_bytes(filename="scope.csv", content=csv_content)
    source_id = response.source.source_id
    repository.set_source_metadata(source_id, year=2015, geography="foreign")

    service = DemoQAService(ledger_repository=repository, run_recorder=repository)
    base_question = "Что делали по Ni-30Cu при старении 700 C 8 ч?"

    ru_only = service.ask(
        AskRequest(question=base_question, filters=AskFilters(geography=["ru"]))
    )
    assert ru_only.experiments == []

    recent = service.ask(
        AskRequest(question=base_question, filters=AskFilters(year_from=2020))
    )
    assert recent.experiments == []

    matching = service.ask(
        AskRequest(
            question=base_question,
            filters=AskFilters(geography=["foreign"], year_from=2010, year_to=2020),
        )
    )
    assert len(matching.experiments) >= 1


def test_numeric_constraint_filters_experiments(repository: DuckDBLedgerRepository) -> None:
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_low,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,210,245,HV,increase\n"
        b"exp_high,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,210,320,HV,increase\n"
    )
    repository.ingest_source_bytes(filename="constraints.csv", content=csv_content)
    service = DemoQAService(ledger_repository=repository, run_recorder=repository)
    response = service.ask(
        AskRequest(question="Твердость Ni-30Cu после старения не более 250 HV")
    )
    values = [experiment.measurement.get("value") for experiment in response.experiments]
    assert values and all(isinstance(v, float) and v <= 250 for v in values)
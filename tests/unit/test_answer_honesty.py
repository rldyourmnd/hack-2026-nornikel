from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.domain.analysis import ConflictDetector
from nornikel_kg.domain.answer_claims import sentence_numbers_supported
from nornikel_kg.domain.models import AskRequest, ExperimentRow
from nornikel_kg.services.qa_service import EvidenceQAService

_CSV = (
    "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
    "property,method,baseline_value,treated_value,unit,effect\n"
    "exp_h1,Медный штейн,aging,700,8,air,Vickers hardness,HV10,210,245,HV,increase\n"
    "exp_h2,Никелевый штейн,annealing,700,1,air,Vickers hardness,HV10,205,215,HV,increase\n"
).encode()


@pytest.fixture()
def repository(tmp_path: Path) -> DuckDBLedgerRepository:
    repo = DuckDBLedgerRepository(tmp_path / "honesty.duckdb")
    repo.migrate()
    repo.ingest_source_bytes(filename="honesty.csv", content=_CSV)
    return repo


def test_irrelevant_question_returns_honest_empty(
    repository: DuckDBLedgerRepository,
) -> None:
    """No arbitrary experiments[:5] with confidence=high (audit C1)."""
    service = EvidenceQAService(ledger_repository=repository, run_recorder=repository)
    response = service.ask(
        AskRequest(question="Какие меры безопасности при работе с печью?")
    )
    assert response.experiments == []
    assert response.confidence == "low"


def test_chemical_formula_is_not_a_material_token(
    repository: DuckDBLedgerRepository,
) -> None:
    """«CO2» must not become an unknown material blanking the answer (audit C4)."""
    service = EvidenceQAService(ledger_repository=repository, run_recorder=repository)
    assert service._requested_material_tokens("Как CO2 влияет на процесс?") == set()
    assert service._requested_material_tokens("выход Al2O3 при обжиге") == set()
    assert service._requested_material_tokens("твердость Ni-30Cu") == {"ni30cu"}


def test_sentence_numbers_supported_catches_fabrication() -> None:
    spans = ["baseline 210 HV | aged 245 HV after 8 h at 700 C"]
    assert sentence_numbers_supported("Твердость выросла до 245 HV.", spans)
    assert not sentence_numbers_supported("Твердость выросла до 999 HV.", spans)
    assert sentence_numbers_supported("Твердость увеличилась.", spans)
    # decimal comma tolerance
    assert sentence_numbers_supported("Доля 0,5 %.", ["содержание 0.5 %"])


def _experiment(
    experiment_id: str,
    regime_id: str,
    value: float,
    *,
    direction: str = "increase",
    method: str = "HV10",
    unit: str = "HV",
    source_id: str = "src_a",
) -> ExperimentRow:
    return ExperimentRow(
        source_id=source_id,
        experiment_id=experiment_id,
        material_id="mat_x",
        material_name="X",
        regime_id=regime_id,
        regime_summary=regime_id,
        property_id="prop_h",
        property_name="hardness",
        measurement={
            "value": value,
            "unit": unit,
            "method": method,
            "effect_direction": direction,
        },
        evidence_ids=[f"span_{experiment_id}"],
        validation_status="validated_rule",
    )


def test_conflict_detector_separates_regime_types() -> None:
    """Aging vs annealing at 700 C are different regimes, not a contradiction."""
    conflicts = ConflictDetector().detect(
        [
            _experiment("e1", "reg_aging_700c_8h", 245.0, direction="increase"),
            _experiment(
                "e2", "reg_annealing_700c_1h", 200.0, direction="decrease", source_id="src_b"
            ),
        ]
    )
    assert all(c["type"] != "contradictory_direction" for c in conflicts)


def test_conflict_detector_requires_same_unit_for_numeric() -> None:
    conflicts = ConflictDetector().detect(
        [
            _experiment("e1", "reg_aging_700c_8h", 245.0, unit="HV"),
            _experiment("e2", "reg_aging_700c_9h", 0.245, unit="ГПа", source_id="src_b"),
        ]
    )
    assert all(c["type"] != "numeric_disagreement" for c in conflicts)


def test_delete_source_cascades_graph_references(tmp_path: Path) -> None:
    """No dangling span ids in entities/relations after source delete (audit H6)."""
    from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument
    from nornikel_kg.services.extraction_service import ExtractionService

    repo = DuckDBLedgerRepository(tmp_path / "cascade.duckdb")
    repo.migrate()
    parsed = ParsedDocument(
        blocks=[
            ParsedBlock(
                text="Обеднение шлака печи Ванюкова снижает потери никеля.",
                page=1,
                locator="block_1",
            )
        ],
        tables=[],
        title="Отчет по шлаку",
        parser_profile="test_v1",
    )
    repo.ingest_parsed_document(
        source_id="src_cascade",
        raw_sha256="2" * 64,
        title="Отчет по шлаку",
        document_type="pdf",
        parsed=parsed,
        artifact_locator="c.pdf",
    )
    ExtractionService(repo, use_gliner=False).process_source("src_cascade")
    deleted_span_ids = {span.span_id for span in repo.list_evidence_spans("src_cascade")}
    assert deleted_span_ids
    assert repo.delete_source("src_cascade")
    for relation in repo.list_graph_relations():
        assert not set(relation["evidence_span_ids"]) & deleted_span_ids
    for entity in repo.list_graph_entities():
        card = repo.get_entity(entity["entity_id"])
        assert card is not None
        assert not set(card["evidence_span_ids"]) & deleted_span_ids


def test_packet_cache_invalidated_by_data_version(
    repository: DuckDBLedgerRepository,
) -> None:
    service = EvidenceQAService(ledger_repository=repository, run_recorder=repository)
    first = service._load_packet()
    assert service._load_packet() is first  # cached while version unchanged
    repository.ingest_source_bytes(filename="bump.md", content=b"new note about slag")
    assert service._load_packet() is not first  # write invalidated the cache



from __future__ import annotations

from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository, SourceIngestError


def test_duckdb_ledger_seeds_synthetic_packet(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    packet = repository.seed_synthetic_fixture(Path("sample_docs/synthetic"))

    assert packet.measurement.value == 245
    assert packet.measurement.unit == "HV"
    assert packet.effect.direction == "increase"
    assert packet.evidence[0].span_type == "table_row"
    assert len(packet.experiments) == 2
    assert packet.conflicts
    assert packet.gaps

    loaded = repository.load_evidence_packet()
    assert loaded.measurement.measurement_id == packet.measurement.measurement_id
    assert loaded.evidence[0].span_id == packet.evidence[0].span_id


def test_duckdb_ledger_ingests_uploaded_csv(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    csv_content = (
        b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        b"property,method,baseline_value,treated_value,unit,effect\n"
        b"exp_upload_nicu,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,200,230,HV,increase\n"
    )

    result = repository.ingest_source_bytes(filename="upload.csv", content=csv_content)

    assert result.warnings == []
    assert result.evidence_count == 1
    assert result.measurement_count == 1
    assert repository.list_evidence_spans(result.source.source_id)[0].span_type == "table_row"


def test_arbitrary_csv_ingests_as_generic_table_with_facts(tmp_path: Path) -> None:
    # A CSV without the fixed experiment schema is no longer rejected: it is
    # ingested as generic header-labeled table rows, and numeric facts are
    # persisted and queryable per span.
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    csv_content = (
        "Показатель,Значение,Ед.изм\nСульфаты,250,мг/л\nСухой остаток,1200,мг/л\n"
    ).encode()

    result = repository.ingest_source_bytes(filename="water_chemistry.csv", content=csv_content)

    assert result.warnings == []
    assert result.evidence_count == 2
    spans = repository.list_evidence_spans(result.source.source_id)
    assert {span.span_type for span in spans} == {"table_row"}

    facts_by_span = repository.list_numeric_facts_for_spans([span.span_id for span in spans])
    values = {
        round(value, 3)
        for entries in facts_by_span.values()
        for _subject, value, _unit in entries
    }
    assert 250.0 in values
    assert 1200.0 in values


def test_uploaded_csv_does_not_steal_seeded_source_facts(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    sample_dir = Path("sample_docs/synthetic")
    repository.seed_synthetic_fixture(sample_dir)

    result = repository.ingest_source_bytes(
        filename="mechanical_properties.csv",
        content=(sample_dir / "mechanical_properties.csv").read_bytes(),
    )

    sources = {source.title: source for source in repository.list_sources()}
    assert sources["Synthetic Ni-Cu aging report"].measurement_count == 2
    assert sources[result.source.title].measurement_count == 2
    assert len(repository.load_evidence_packet().experiments) == 4


def test_upload_invalid_csv_does_not_invent_source(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    initial_sources = repository.list_sources()
    bad_csv = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
        "exp_fail,Ni-30Cu,aging,not-a-number,8,air,Vickers hardness,HV10,200,230,HV,increase\n"
    )

    with pytest.raises(SourceIngestError):
        repository.ingest_source_bytes(filename="bad.csv", content=bad_csv.encode())

    assert repository.list_sources() == initial_sources


def test_delete_source_returns_expected_result(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "catalog.duckdb")
    result = repository.ingest_source_bytes(
        filename="deletable.csv",
        content=(
            b"experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
            b"property,method,baseline_value,treated_value,unit,effect\n"
            b"exp_delete,Ni-30Cu,aging,700,8,air,Vickers hardness,HV10,200,230,HV,increase\n"
        ),
    )

    source_id = result.source.source_id
    assert repository.delete_source(source_id)
    assert not repository.delete_source(source_id)

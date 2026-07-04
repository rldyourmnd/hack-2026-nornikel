from __future__ import annotations

from pathlib import Path

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.domain.models import EvidenceSpan
from nornikel_kg.domain.quantities import (
    facts_satisfy_constraints,
    parse_parameter_constraints,
)
from nornikel_kg.services.qa_service import EvidenceQAService

_MULTI = (
    "Какие методы обессоливания при сульфаты, хлориды, Ca, Mg, Na по 200-300 мг/л, "
    "сухой остаток не более 1000 мг/дм3?"
)


def test_multi_analyte_range_binds_each_species() -> None:
    constraints = parse_parameter_constraints(_MULTI)
    subjects = {c.subject for c in constraints}
    assert {"сульфаты", "хлориды", "кальций", "магний", "натрий"} <= subjects
    assert "сухой остаток" in subjects
    dry = [c for c in constraints if c.subject == "сухой остаток"]
    assert dry and dry[0].op == "<=" and dry[0].value == 1000.0 and dry[0].unit == "мг/л"


def test_facts_satisfy_when_species_in_range() -> None:
    constraints = parse_parameter_constraints(
        "сульфаты по 200-300 мг/л, сухой остаток до 1000 мг/дм3"
    )
    facts_ok = [("сульфаты", 280.0, "мг/л"), ("сухой остаток", 950.0, "мг/л")]
    assert facts_satisfy_constraints(facts_ok, constraints)
    facts_bad = [("сульфаты", 280.0, "мг/л"), ("сухой остаток", 1200.0, "мг/л")]
    assert not facts_satisfy_constraints(facts_bad, constraints)


def test_absent_species_is_not_a_violation() -> None:
    constraints = parse_parameter_constraints("сухой остаток до 1000 мг/дм3")
    assert facts_satisfy_constraints([("хлориды", 250.0, "мг/л")], constraints)


def test_year_phrase_is_not_a_parameter_constraint() -> None:
    assert parse_parameter_constraints("что делали до 2020 года") == []


def test_qa_drops_evidence_that_violates_dry_residue(tmp_path: Path) -> None:
    repo = DuckDBLedgerRepository(tmp_path / "pc.duckdb")
    repo.migrate()
    service = EvidenceQAService(ledger_repository=repo, run_recorder=repo)
    good = EvidenceSpan(
        span_id="s_ok",
        source_id="src",
        artifact_id="a",
        span_type="table_row",
        visible_text="Компонент: Вода | Сухой остаток, мг/дм3: 950",
    )
    bad = EvidenceSpan(
        span_id="s_bad",
        source_id="src",
        artifact_id="a",
        span_type="table_row",
        visible_text="Компонент: Вода | Сухой остаток, мг/дм3: 1200",
    )
    kept = service._drop_constraint_violating_evidence(
        "методы при сухой остаток не более 1000 мг/дм3", [good, bad]
    )
    ids = {span.span_id for span in kept}
    assert "s_ok" in ids and "s_bad" not in ids

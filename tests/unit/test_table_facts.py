from __future__ import annotations

from nornikel_kg.domain.table_facts import (
    extract_facts_from_row,
    parse_labeled_span_facts,
)


def test_wide_water_chemistry_table_binds_analyte_to_value() -> None:
    headers = ["Компонент", "Сульфаты, мг/л", "Хлориды, мг/л", "Сухой остаток, мг/дм3"]
    values = ["Вода оборотная", "280", "210", "950"]
    facts = extract_facts_from_row(headers, values)
    by_subject = {f.prop: (f.value, f.unit) for f in facts}
    assert by_subject["сульфаты"] == (280.0, "мг/л")
    assert by_subject["хлориды"] == (210.0, "мг/л")
    # мг/дм3 canonicalizes to мг/л
    assert by_subject["сухой остаток"] == (950.0, "мг/л")


def test_tall_table_subject_value_unit_columns() -> None:
    headers = ["Показатель", "Значение", "Ед.изм"]
    values = ["Скорость циркуляции", "185", "см3/мин"]
    facts = extract_facts_from_row(headers, values)
    assert len(facts) == 1
    assert facts[0].subject_label == "Скорость циркуляции"
    assert facts[0].value == 185.0


def test_parse_labeled_span_facts_roundtrip() -> None:
    span = "Компонент: Вода | Сульфаты, мг/л: 300 | Хлориды, мг/л: 250"
    facts = parse_labeled_span_facts(span)
    props = {f.prop: f.value for f in facts}
    assert props["сульфаты"] == 300.0
    assert props["хлориды"] == 250.0


def test_row_without_numbers_yields_nothing() -> None:
    assert extract_facts_from_row(["Материал", "Примечание"], ["штейн", "нет данных"]) == []

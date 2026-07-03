from __future__ import annotations

from nornikel_kg.domain.dates import extract_date, extract_year, extract_year_from_filename
from nornikel_kg.domain.normalization import canonical_key
from nornikel_kg.domain.quantities import (
    NumericConstraint,
    normalize_unit,
    parse_numeric_constraints,
    satisfies_constraints,
)


def test_unit_equivalence_mg_dm3_is_mg_l() -> None:
    assert normalize_unit("мг/дм³") == "мг/л"
    assert normalize_unit("мг/дм3") == "мг/л"
    assert normalize_unit("МГ / Л") == "мг/л"
    assert normalize_unit("г/дм³") == "г/л"
    assert normalize_unit("°С") == "c"  # Cyrillic С
    assert normalize_unit("°C") == "c"  # Latin C


def test_year_phrases_do_not_become_constraints() -> None:
    """«до 2020 года» must never filter measurement values (audit H3)."""
    assert parse_numeric_constraints("покажите работы до 2020 года") == []
    assert parse_numeric_constraints("за последние 5 лет по МПГ") == []


def test_range_from_to_with_unit() -> None:
    constraints = parse_numeric_constraints("концентрация от 100 до 300 мг/л")
    assert NumericConstraint(">=", 100.0, "мг/л") in constraints
    assert NumericConstraint("<=", 300.0, "мг/л") in constraints


def test_cross_unit_constraint_filters_equivalent_units() -> None:
    constraints = parse_numeric_constraints("сухой остаток не более 1000 мг/дм³")
    # measurement stored as мг/л — physically the same unit
    assert not satisfies_constraints(1500.0, "мг/л", constraints)
    assert satisfies_constraints(800.0, "мг/л", constraints)
    # different unit is never silently compared
    assert satisfies_constraints(1500.0, "HV", constraints)


def test_unitless_measurement_kept() -> None:
    constraints = parse_numeric_constraints("не более 300 мг/л")
    assert satisfies_constraints(999.0, None, constraints)
    assert satisfies_constraints("н/д", "мг/л", constraints)


def test_extract_date_ru_text_and_iso() -> None:
    year, date = extract_date("Протокол утвержден 12 марта 2023 г. в Норильске")
    assert (year, date) == (2023, "2023-03-12")
    year, date = extract_date("Report generated on 2021-06-30 by the lab")
    assert (year, date) == (2021, "2021-06-30")


def test_extract_year_requires_marker_for_bare_numbers() -> None:
    assert extract_year("температура достигала 1963 K при плавке") is None
    assert extract_year("Цветные металлы, 2019 г., № 4") == 2019


def test_extract_year_from_filename() -> None:
    assert extract_year_from_filename("slag_depletion_2018_final.pdf") == 2018
    assert extract_year_from_filename("report_v2.docx") is None


def test_canonical_key_folds_homoglyphs_and_quotes() -> None:
    # Cyrillic С typed inside a technical token folds to Latin c
    assert canonical_key("Ni-30Сu") == canonical_key("Ni-30Cu")
    assert canonical_key("«старение»") == canonical_key("старение")
    # pure-Cyrillic words stay untouched
    assert canonical_key("СОСТАВ") == "состав"

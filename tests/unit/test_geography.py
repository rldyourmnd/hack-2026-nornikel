from __future__ import annotations

from nornikel_kg.domain.geography import detect_geography


def test_russian_language_foreign_practice_is_foreign() -> None:
    # Russian-language text describing Finnish (Aalto) practice
    text = "В работе учёных университета Aalto (Finland) исследовано распределение металлов."
    assert detect_geography(text) == "foreign"


def test_english_norilsk_paper_is_ru() -> None:
    text = "This study at Norilsk Nickel (Kola MMC) reports slag depletion results in detail."
    assert detect_geography(text) == "ru"


def test_mixed_signals() -> None:
    text = "Сравнение практики Норильск и Sudbury (Canada) по обеднению шлака в печах."
    assert detect_geography(text) == "mixed"


def test_language_fallback_without_country_signal() -> None:
    ru_text = "Обеднение шлака снижает потери никеля в расплаве значительно."
    en_text = "Slag depletion reduces nickel losses in the melt substantially."
    assert detect_geography(ru_text) == "ru"
    assert detect_geography(en_text) == "foreign"


def test_too_short_is_unknown() -> None:
    assert detect_geography("шлак") is None

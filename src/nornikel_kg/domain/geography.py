from __future__ import annotations

import re

# Practice geography from country/affiliation signals, not document language.
# A Russian-language review of Finnish practice is "foreign"; an English paper
# from Norilsk Nickel is "ru". Script is only a last-resort tiebreak.

_RU_SIGNALS = (
    "россия",
    "российск",
    "рф",
    "норильск",
    "мончегорск",
    "заполярн",
    "кольск",
    "гмк",
    "норникель",
    "nornickel",
    "norilsk",
    "kola",
    "россии",
    "оао",
    "пао",
    "фгуп",
    "гипроникель",
    "санкт-петербург",
    "москва",
    "екатеринбург",
)

_FOREIGN_SIGNALS = (
    "finland",
    "aalto",
    "sweden",
    "norway",
    "canada",
    "sudbury",
    "long harbour",
    "australia",
    "china",
    "japan",
    "germany",
    "usa",
    "united states",
    "south africa",
    "финлянд",
    "швеци",
    "канад",
    "австрал",
    "китай",
    "япони",
    "герман",
    "уэльва",
    "huelva",
    "outokumpu",
    "vale",
    "glencore",
    "boliden",
)


def _has_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def detect_geography(head_text: str) -> str | None:
    """Return 'ru' | 'foreign' | 'mixed' | None for a document's head text.

    Country/organization/location signals decide first; only when neither side
    is named does the Cyrillic-vs-Latin script ratio break the tie. None means
    too little signal to label (kept out of geography filters honestly).
    """
    low = head_text.lower()
    ru = _has_any(low, _RU_SIGNALS)
    foreign = _has_any(low, _FOREIGN_SIGNALS)
    if ru and foreign:
        return "mixed"
    if ru:
        return "ru"
    if foreign:
        return "foreign"
    # No location signal — fall back to the language of the text.
    cyrillic = len(re.findall(r"[а-яё]", low))
    latin = len(re.findall(r"[a-z]", low))
    if cyrillic + latin <= 40:
        return None
    return "ru" if cyrillic >= latin else "foreign"

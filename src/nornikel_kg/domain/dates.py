from __future__ import annotations

import re

# Deterministic RU/EN date extraction: narrow candidate regexes only, never a
# fuzzy full-text date search (dateparser.search_dates is documented to emit
# false positives on scientific prose).

_RU_MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "мая": 5,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}

_EN_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

MIN_YEAR = 1950
MAX_YEAR = 2027

_ISO_RE = re.compile(r"\b(?P<y>(?:19|20)\d{2})-(?P<m>0[1-9]|1[0-2])-(?P<d>0[1-9]|[12]\d|3[01])\b")
_DMY_RE = re.compile(
    r"\b(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>(?:19|20)\d{2})\b"
)
_RU_TEXT_RE = re.compile(
    r"\b(?:(?P<d>0?[1-9]|[12]\d|3[01])\s+)?(?P<month>[а-яё]{3,8})[а-яё]*\s+(?P<y>(?:19|20)\d{2})",
    re.IGNORECASE,
)
_EN_TEXT_RE = re.compile(
    r"\b(?P<month>[A-Za-z]{3,9})\.?\s+(?:(?P<d>0?[1-9]|[12]\d|3[01]),?\s+)?(?P<y>(?:19|20)\d{2})\b"
)
# Bare year: must not be part of a measurement («1963 K», «2040 °C») and gains
# trust from an adjacent year marker («2023 г.», «в 2019 году», © 2021).
_BARE_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b(?!\s*(?:[KКк]\b|°|гц|hz|мм|нм|см))")
_YEAR_MARKER_RE = re.compile(r"(?:19|20)\d{2}\s*(?:г\.|гг\.|год[ау]?|году)|©\s*(?:19|20)\d{2}")


def _in_bounds(year: int) -> bool:
    return MIN_YEAR <= year <= MAX_YEAR


def extract_date(text: str) -> tuple[int | None, str | None]:
    """Best (year, ISO date) found in text; date component may be None.

    Full dates win over month-year, month-year wins over bare years; bare
    years are only trusted next to an explicit year marker.
    """
    for match in _ISO_RE.finditer(text):
        year = int(match.group("y"))
        if _in_bounds(year):
            return year, f"{year:04d}-{int(match.group('m')):02d}-{int(match.group('d')):02d}"
    for match in _DMY_RE.finditer(text):
        year = int(match.group("y"))
        if _in_bounds(year):
            return year, f"{year:04d}-{int(match.group('m')):02d}-{int(match.group('d')):02d}"
    for match in _RU_TEXT_RE.finditer(text):
        month_stem = match.group("month").lower()
        month = next((m for stem, m in _RU_MONTHS.items() if month_stem.startswith(stem)), None)
        year = int(match.group("y"))
        if month is not None and _in_bounds(year):
            day = int(match.group("d") or 1)
            return year, f"{year:04d}-{month:02d}-{day:02d}"
    for match in _EN_TEXT_RE.finditer(text):
        month = _EN_MONTHS.get(match.group("month").lower()[:3])
        year = int(match.group("y"))
        if month is not None and _in_bounds(year):
            day = int(match.group("d") or 1)
            return year, f"{year:04d}-{month:02d}-{day:02d}"
    return extract_year(text), None


def extract_year(text: str) -> int | None:
    """Most recent plausible publication year in text, or None.

    Bare 4-digit numbers are counted only when the text also carries a year
    marker («2023 г.», «в ... году», ©) — otherwise sample codes, Kelvin
    temperatures, and forecast horizons masquerade as years.
    """
    candidates = [int(m.group(1)) for m in _BARE_YEAR_RE.finditer(text)]
    candidates = [year for year in candidates if _in_bounds(year)]
    if not candidates:
        return None
    if _YEAR_MARKER_RE.search(text) or _ISO_RE.search(text) or _DMY_RE.search(text):
        return max(candidates)
    return None


def extract_year_from_filename(filename: str) -> int | None:
    """Year embedded in a filename (common for conference/journal scans)."""
    candidates = [
        int(match.group(1)) for match in re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", filename)
    ]
    candidates = [year for year in candidates if _in_bounds(year)]
    return max(candidates) if candidates else None

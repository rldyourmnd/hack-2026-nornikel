from __future__ import annotations

import re
from dataclasses import dataclass

from nornikel_kg.domain.normalization import canonical_key
from nornikel_kg.domain.quantities import normalize_unit

# Generic structured-fact extraction from header-labeled table rows. Real
# corpus tables (water chemistry, distribution coefficients, techno-economics)
# encode a subject + a measured value + a unit; this turns any headered row into
# subject-tagged numeric facts that answer/constraint matching can use, while
# staying conservative: a fact is emitted only when a number is present.

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_UNIT_IN_HEADER_RE = re.compile(r"[,(]\s*([^,()]+?)\s*\)?$")
# Headers that name the measured subject rather than a value column.
_SUBJECT_HEADER_HINTS = (
    "показател",
    "компонент",
    "параметр",
    "вещество",
    "элемент",
    "ион",
    "материал",
    "образец",
    "проба",
    "metric",
    "parameter",
    "component",
    "material",
    "sample",
    "element",
)
_VALUE_HEADER_HINTS = ("значен", "содержан", "концентрац", "value", "content", "concentration")
_UNIT_HEADER_HINTS = ("ед.изм", "единиц", "unit", "размерн")

# Known non-unit strings that appear in spreadsheet headers/parentheses but
# are NOT physical units. These are country names, location qualifiers, or
# table annotations that were misidentified as units in the 300-file ingest.
_NON_UNIT_TOKENS = frozenset({
    "japan", "russia", "australia", "belgium", "germany", "china", "anhuichina",
    "txusa", "000t", "kazakhstan", "canada", "finland", "norway", "sweden",
    "usa", "uk", "france", "italy", "spain", "poland", "india", "brazil",
    "mexico", "chile", "peru", "zambia", "congo", "morocco", "south africa",
    "new caledonia", "indonesia", "philippines", "zimbabwe", "botswana",
    "namibia", "mongolia", "iran", "turkey", "korea", "ukraine", "belarus",
    "arctic", "siberia", "ural", "kola",
})

# Valid unit patterns: must contain a digit, a unit symbol, or a known
# measurement keyword. Pure word strings (country names, locations) are rejected.
_UNIT_KEYWORDS = (
    "мг", "г", "кг", "т", "мл", "л", "м3", "м²", "м", "мм", "см", "км",
    "па", "кпа", "мпа", "бар", "атм", "руб", "долл", "$", "eur", "usd",
    "час", "ч", "мин", "сут", "год", "лет", "мес",
    "%", "град", "°", "c", "k", "f", "ppm", "ppb",
    "вт", "квт", "мвт", "дж", "кал", "гц",
    "мкг", "нг", "моль", "ммоль", "экв",
    "mg", "g", "kg", "t", "ml", "l", "m", "mm", "cm", "km",
    "pa", "kpa", "mpa", "bar", "atm", "rub", "usd", "eur",
    "h", "min", "day", "year", "mo",
    "ppm", "ppb", "kv", "kw", "mw", "j", "cal",
    "ug", "ng", "mol", "mmol", "eq",
    "отн", "ед", "раз", "доля", "tier", "class",
)

_UNIT_MIN_LENGTH = 1
_UNIT_MAX_LENGTH = 20


def _is_valid_unit(token: str) -> bool:
    """Check if a token looks like a real physical unit, not a country name or random word."""
    if not token or len(token) > _UNIT_MAX_LENGTH:
        return False
    low = token.lower().strip()
    if low in _NON_UNIT_TOKENS:
        return False
    if any(non in low for non in ("japan", "russia", "china", "germany", "korea",
                                   "australia", "belgium", "canada", "finland")):
        return False
    return any(kw in low for kw in _UNIT_KEYWORDS)


@dataclass(frozen=True)
class NumericFact:
    subject: str  # canonical subject token (e.g. "сульфаты", "au")
    subject_label: str  # human-readable subject as written
    prop: str  # property/measurement name (from header or value column)
    value: float
    unit: str  # canonical unit ("" when unitless)


def _to_float(text: str) -> float | None:
    match = _NUMBER_RE.search(text.replace(" ", " "))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _unit_from_header(header: str) -> str:
    match = _UNIT_IN_HEADER_RE.search(header)
    if match:
        raw_unit = normalize_unit(match.group(1))
        if _is_valid_unit(raw_unit):
            return raw_unit
    return ""


def _header_role(header: str) -> str:
    low = header.lower()
    if any(hint in low for hint in _UNIT_HEADER_HINTS):
        return "unit"
    if any(hint in low for hint in _VALUE_HEADER_HINTS):
        return "value"
    if any(hint in low for hint in _SUBJECT_HEADER_HINTS):
        return "subject"
    return "other"


def extract_facts_from_row(
    headers: list[str], values: list[str]
) -> list[NumericFact]:
    """Subject-tagged numeric facts from one header-labeled table row.

    Two shapes are handled: (a) tall tables — a subject column + a value column
    (+ optional unit column); (b) wide tables — a subject column plus one
    numeric column per property, the unit read from the property header.
    """
    if not headers:
        return []
    roles = [_header_role(h) for h in headers]
    subject_idx = next((i for i, r in enumerate(roles) if r == "subject"), None)
    value_idx = next((i for i, r in enumerate(roles) if r == "value"), None)
    unit_idx = next((i for i, r in enumerate(roles) if r == "unit"), None)

    def cell(i: int | None) -> str:
        return values[i].strip() if i is not None and i < len(values) else ""

    facts: list[NumericFact] = []
    # Tall shape: explicit subject + value columns.
    if subject_idx is not None and value_idx is not None:
        subject_label = cell(subject_idx)
        number = _to_float(cell(value_idx))
        if subject_label and number is not None:
            raw_unit = normalize_unit(cell(unit_idx)) or _unit_from_header(headers[value_idx])
            unit = raw_unit if _is_valid_unit(raw_unit) else ""
            facts.append(
                NumericFact(
                    subject=canonical_key(subject_label),
                    subject_label=subject_label,
                    prop=canonical_key(headers[value_idx]) or "value",
                    value=number,
                    unit=unit,
                )
            )
        return facts

    # Wide shape: first non-numeric cell is the subject; each numeric column is
    # a property carrying its own header (and unit-in-header).
    subject_label = ""
    for i, value in enumerate(values):
        if _to_float(value) is None and value.strip():
            subject_label = value.strip()
            subject_idx = i
            break
    if not subject_label:
        return facts
    for i, (header, value) in enumerate(zip(headers, values, strict=False)):
        if i == subject_idx or not header.strip():
            continue
        number = _to_float(value)
        if number is None:
            continue
        raw_unit = _unit_from_header(header)
        unit = raw_unit if _is_valid_unit(raw_unit) else ""
        facts.append(
            NumericFact(
                subject=canonical_key(subject_label),
                subject_label=subject_label,
                prop=canonical_key(re.sub(_UNIT_IN_HEADER_RE, "", header).strip()) or "value",
                value=number,
                unit=unit,
            )
        )
    return facts


def parse_labeled_span_facts(span_text: str) -> list[NumericFact]:
    """Reconstruct numeric facts from a stored header-labeled table-row span.

    Table-row spans persist as "Header: value | Header2: value2"; recovering
    (header, value) pairs lets query-time constraint matching run over evidence
    without a separate fact store.
    """
    pairs = [segment for segment in span_text.split(" | ") if ":" in segment]
    if not pairs:
        return []
    headers = [pair.split(":", 1)[0].strip() for pair in pairs]
    values = [pair.split(":", 1)[1].strip() for pair in pairs]
    return extract_facts_from_row(headers, values)

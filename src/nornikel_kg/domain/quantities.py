from __future__ import annotations

import re
from dataclasses import dataclass

# Unit canonicalization. Physically equivalent spellings collapse to one
# canonical token so that «сухой остаток ≤1000 мг/дм³» matches measurements
# stored as «мг/л» (1 дм³ = 1 л). Cyrillic homoglyphs («с» vs "c") fold too.
_UNIT_EQUIVALENCE: dict[str, str] = {
    "мг/дм3": "мг/л",
    "мг/дм³": "мг/л",
    "мг/l": "мг/л",
    "mg/l": "мг/л",
    "mg/dm3": "мг/л",
    "г/дм3": "г/л",
    "г/дм³": "г/л",
    "g/l": "г/л",
    "кг/м3": "г/л",
    "кг/м³": "г/л",
    "м³/ч": "м3/ч",
    "m3/h": "м3/ч",
    "°с": "c",
    "°c": "c",
    "℃": "c",
    "гр/т": "г/т",
    "g/t": "г/т",
}

_UNIT_STRIP_RE = re.compile(r"\s+")


def normalize_unit(unit: str) -> str:
    """Canonical unit token: lowercase, no spaces, superscripts and homoglyph
    variants folded, physically equivalent spellings collapsed."""
    token = _UNIT_STRIP_RE.sub("", unit.lower())
    token = token.replace("³", "3").replace("²", "2")
    # Latin homoglyphs typed as Cyrillic in unit strings ("c" for Celsius).
    if token in {"с", "°с"}:
        token = "c"
    return _UNIT_EQUIVALENCE.get(token, token)


@dataclass(frozen=True)
class NumericConstraint:
    op: str  # "<=" | ">="
    value: float
    unit: str  # canonical, never empty


# Units we recognize inside questions. Longest-first alternation.
_UNIT_PATTERN = (
    r"мг/дм3|мг/дм³|мг/л|г/дм3|г/дм³|г/л|г/т|гр/т|кг/м3|кг/м³|мг/кг|"
    r"м3/ч|м³/ч|л/мин|л/ч|м/с|т/сут|т/ч|мпа|кпа|па|hv|hrc|"
    r"°c|°с|%|ч|мин|сут"
)

_VALUE_PATTERN = r"\d+(?:[.,]\d+)?"

_RANGE_RE = re.compile(
    rf"(?:в\s+(?:диапазоне|пределах)\s+)?от\s*(?P<low>{_VALUE_PATTERN})\s*"
    rf"до\s*(?P<high>{_VALUE_PATTERN})\s*(?P<unit>{_UNIT_PATTERN})?",
    re.IGNORECASE,
)

_SINGLE_RE = re.compile(
    rf"(?P<op>≤|<=|<|не более|не выше|не превышает|менее|ниже|до|"
    rf"≥|>=|>|не менее|не ниже|более|выше|свыше|от)\s*"
    rf"(?P<value>{_VALUE_PATTERN})\s*(?P<unit>{_UNIT_PATTERN})?",
    re.IGNORECASE,
)

_LE_OPS = {"≤", "<=", "<", "не более", "не выше", "не превышает", "менее", "ниже", "до"}


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def parse_numeric_constraints(question: str) -> list[NumericConstraint]:
    """Unit-bearing numeric constraints from a natural-language question.

    Precision-first contract: a constraint without an explicit recognized
    unit is NOT returned — otherwise phrases like «до 2020 года» or «за
    последние 5 лет» would silently filter out valid measurements of
    unrelated properties.
    """
    constraints: list[NumericConstraint] = []
    consumed = question

    for match in _RANGE_RE.finditer(question):
        unit_raw = match.group("unit")
        if not unit_raw:
            continue
        unit = normalize_unit(unit_raw)
        constraints.append(NumericConstraint(">=", _to_float(match.group("low")), unit))
        constraints.append(NumericConstraint("<=", _to_float(match.group("high")), unit))
        consumed = consumed.replace(match.group(0), " " * len(match.group(0)), 1)

    for match in _SINGLE_RE.finditer(consumed):
        unit_raw = match.group("unit")
        if not unit_raw:
            continue
        op = "<=" if match.group("op").lower() in _LE_OPS else ">="
        constraints.append(
            NumericConstraint(op, _to_float(match.group("value")), normalize_unit(unit_raw))
        )
    return constraints


def satisfies_constraints(
    value: object,
    unit: object,
    constraints: list[NumericConstraint],
) -> bool:
    """True when a (value, unit) measurement passes every matching constraint.

    Only constraints whose canonical unit equals the measurement's canonical
    unit are applied; non-numeric values and unit mismatches keep the row
    (honest recall over silent precision loss).
    """
    if not isinstance(value, int | float) or isinstance(value, bool):
        return True
    measurement_unit = normalize_unit(str(unit or ""))
    if not measurement_unit:
        return True
    for constraint in constraints:
        if constraint.unit != measurement_unit:
            continue
        if constraint.op == "<=" and value > constraint.value:
            return False
        if constraint.op == ">=" and value < constraint.value:
            return False
    return True

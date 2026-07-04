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
    "квт·ч/т": "квтч/т",
    "kwh/t": "квтч/т",
    "mkg/l": "мкг/л",
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
    subject: str = ""  # canonical subject token ("" = applies to any subject)


# Analyte / parameter subjects recognized in questions, mapped to a canonical
# token. Multi-analyte water-chemistry questions («сульфаты, хлориды, Ca, Mg,
# Na по 200–300 мг/л») need each number bound to its species, not just its unit.
_SUBJECT_ALIASES: dict[str, str] = {
    "сульфат": "сульфаты",
    "sulfate": "сульфаты",
    "so4": "сульфаты",
    "хлорид": "хлориды",
    "chloride": "хлориды",
    "cl": "хлориды",
    "кальци": "кальций",
    "calcium": "кальций",
    "ca": "кальций",
    "магни": "магний",
    "magnesium": "магний",
    "mg": "магний",
    "натри": "натрий",
    "sodium": "натрий",
    "na": "натрий",
    "сухой остаток": "сухой остаток",
    "dry residue": "сухой остаток",
    "минерализац": "сухой остаток",
    "скорость потока": "скорость потока",
    "скорость циркуляц": "скорость потока",
    "расход": "скорость потока",
    "flow": "скорость потока",
    "температур": "температура",
    "temperature": "температура",
    "производительн": "производительность",
    "productivity": "производительность",
    "capex": "capex",
    "opex": "opex",
    "глубин": "глубина",
    "depth": "глубина",
}


# Units we recognize inside questions. Longest-first alternation.
_UNIT_PATTERN = (
    r"мг/дм3|мг/дм³|мг/л|мкг/л|г/дм3|г/дм³|г/л|г/т|гр/т|кг/м3|кг/м³|мг/кг|"
    r"руб/м³|руб/м3|руб/т|млн руб|\$/т|квт·ч/т|квтч/т|"
    r"м³/сут|м3/сут|м³/ч|м3/ч|м/сут|м/с|л/мин|л/ч|т/сут|т/ч|ppm|"
    r"мпа|кпа|па|hv|hrc|°c|°с|%|ч|мин|сут"
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


def _subjects_before(text: str) -> list[str]:
    """Canonical subject tokens mentioned in a text fragment (order-preserving)."""
    low = text.lower()
    found: list[str] = []
    for alias, canonical in _SUBJECT_ALIASES.items():
        # Word-ish boundary for short chemical symbols so "na" doesn't match
        # inside "начало"; longer aliases match as substrings.
        if len(alias) <= 3:
            if re.search(rf"(?<![а-яёa-z]){re.escape(alias)}(?![а-яёa-z])", low) and (
                canonical not in found
            ):
                found.append(canonical)
        elif alias in low and canonical not in found:
            found.append(canonical)
    return found


def parse_parameter_constraints(question: str) -> list[NumericConstraint]:
    """Subject-bound numeric constraints from a question.

    Binds each numeric range/bound to the analyte/parameter subjects that
    precede it, so «сульфаты, хлориды, Ca, Mg, Na по 200–300 мг/л, сухой
    остаток ≤1000 мг/дм³» yields per-species constraints instead of one
    unit-only rule that collides across species. A constraint with no
    resolvable subject keeps subject="" (matches any subject, as before).
    """
    constraints: list[NumericConstraint] = []
    # Segment the question at each numeric-bound clause; subjects named since
    # the previous clause bind to this clause's constraint.
    spans: list[tuple[int, int, list[NumericConstraint]]] = []
    for match in _RANGE_RE.finditer(question):
        if not match.group("unit"):
            continue
        unit = normalize_unit(match.group("unit"))
        spans.append(
            (
                match.start(),
                match.end(),
                [
                    NumericConstraint(">=", _to_float(match.group("low")), unit),
                    NumericConstraint("<=", _to_float(match.group("high")), unit),
                ],
            )
        )
    range_spans = [(s, e) for s, e, _ in spans]
    for match in _SINGLE_RE.finditer(question):
        if not match.group("unit"):
            continue
        if any(s <= match.start() < e for s, e in range_spans):
            continue  # already covered by a range match
        op = "<=" if match.group("op").lower() in _LE_OPS else ">="
        spans.append(
            (
                match.start(),
                match.end(),
                [
                    NumericConstraint(
                        op,
                        _to_float(match.group("value")),
                        normalize_unit(match.group("unit")),
                    )
                ],
            )
        )
    spans.sort(key=lambda item: item[0])
    prev_end = 0
    for start, end, clause in spans:
        subjects = _subjects_before(question[prev_end:start])
        for base in clause:
            if subjects:
                for subject in subjects:
                    constraints.append(
                        NumericConstraint(base.op, base.value, base.unit, subject)
                    )
            else:
                constraints.append(base)
        prev_end = end
    return constraints


def facts_satisfy_constraints(
    facts: list[tuple[str, float, str]],
    constraints: list[NumericConstraint],
) -> bool:
    """True when subject-bound constraints are all satisfied by the facts.

    `facts` are (canonical_subject, value, canonical_unit). A subject-bound
    constraint must find at least one same-subject same-unit fact in range;
    a subjectless constraint falls back to unit-only matching. Constraints
    with no candidate fact at all are treated as satisfied (honest recall —
    absence of data is not a violation).
    """
    for constraint in constraints:
        candidates = [
            (subject, value, unit)
            for subject, value, unit in facts
            if unit == constraint.unit
            and (not constraint.subject or subject == constraint.subject)
        ]
        if not candidates:
            continue
        ok = any(
            (constraint.op == "<=" and value <= constraint.value)
            or (constraint.op == ">=" and value >= constraint.value)
            for _subject, value, unit in candidates
        )
        if not ok:
            return False
    return True


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

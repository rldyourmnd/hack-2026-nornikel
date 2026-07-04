from __future__ import annotations

import re

_DASH_VARIANTS_RE = re.compile(r"[‐‑‒–—―−_]")
_WHITESPACE_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\"'«»„“”()\[\]{}.,:;!?]+|[\s\"'«»„“”()\[\]{}.,:;!?]+$")
_LATIN_RE = re.compile(r"[a-z]")

# Cyrillic letters whose glyphs are identical to Latin ones. Scientific texts
# routinely mix them inside one token («700 С», «Ni-30Сu» typed with Cyrillic
# С), which silently splits entities and units into distinct canonical keys.
_HOMOGLYPH_CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "в": "b",
        "е": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "у": "y",
        "х": "x",
    }
)


def _fold_homoglyphs(token: str) -> str:
    """Fold Cyrillic homoglyphs to Latin, but only in genuinely mixed-script tokens.

    Only tokens that carry BOTH a Latin letter AND a Cyrillic letter fold
    («Ni-30Сu» typed with Cyrillic С). Pure-Cyrillic tokens — including
    alloy codes like «МН30» and words split by hyphens — stay Cyrillic: they
    are legitimate Russian designations resolved through the alias table,
    not typos. A token like «постоянным» must never fold even if a dash split
    made an adjacent part appear Latin-only.
    """
    has_cyrillic = bool(re.search(r"[а-яё]", token))
    has_latin = bool(_LATIN_RE.search(token))
    if has_cyrillic and has_latin:
        return token.translate(_HOMOGLYPH_CYR_TO_LAT)
    return token


def canonical_key(value: str) -> str:
    """Normalize an entity mention into its canonical resolution key.

    Rules fixed by the entity-resolution contract: lowercase, strip edge
    quotes/punctuation, unify every dash variant to "-", fold "ё" to "е",
    fold Cyrillic/Latin homoglyphs inside technical tokens, collapse
    whitespace runs.
    """
    normalized = _DASH_VARIANTS_RE.sub("-", value.strip().lower())
    normalized = normalized.replace("ё", "е")
    normalized = _EDGE_PUNCT_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return " ".join(_fold_homoglyphs(token) for token in normalized.split(" "))

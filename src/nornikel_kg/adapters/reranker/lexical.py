from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{2,}")
_STOPWORDS = {
    "без",
    "для",
    "или",
    "как",
    "какая",
    "какие",
    "какой",
    "над",
    "при",
    "про",
    "что",
    "это",
}
_RU_SUFFIXES = (
    "иями",
    "ями",
    "ами",
    "ого",
    "ему",
    "ими",
    "ыми",
    "иях",
    "ах",
    "ях",
    "ов",
    "ев",
    "ия",
    "ий",
    "ый",
    "ой",
    "ая",
    "ое",
    "ые",
    "ых",
    "ам",
    "ям",
    "ом",
    "ем",
    "ия",
    "ие",
    "ии",
    "и",
    "ы",
    "а",
    "я",
    "е",
    "у",
    "ю",
)


def _normalize_token(token: str) -> str:
    token = token.lower().replace("ё", "е")
    if token.isdigit() or len(token) <= 4:
        return token
    for suffix in _RU_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 4:
            return token[: -len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    return [
        normalized
        for token in _TOKEN_RE.findall(text)
        if (normalized := _normalize_token(token)) not in _STOPWORDS
    ]


class LexicalReranker:
    """Small CPU-only reranker for Russian technical QA.

    It reranks the Qdrant fused candidates with exact token, number, and short
    phrase evidence. It deliberately avoids model loading, GPU runtimes, and
    ONNX export; Qdrant remains the semantic recall stage.
    """

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str]],
        *,
        top_k: int,
    ) -> list[str]:
        if not candidates:
            return []
        query_terms = Counter(_tokens(query))
        if not query_terms:
            return [unit_id for unit_id, _ in candidates[:top_k]]
        query_numbers = {term for term in query_terms if term.isdigit()}
        scored: list[tuple[float, int, str]] = []
        for index, (unit_id, text) in enumerate(candidates):
            scored.append((self._score(query, query_terms, query_numbers, text), index, unit_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [unit_id for _, _, unit_id in scored[:top_k]]

    def _score(
        self,
        query: str,
        query_terms: Counter[str],
        query_numbers: set[str],
        text: str,
    ) -> float:
        text_terms = Counter(_tokens(text))
        if not text_terms:
            return 0.0
        overlap = 0.0
        for term, query_count in query_terms.items():
            term_count = text_terms.get(term, 0)
            if term_count == 0:
                continue
            if term.isdigit():
                weight = 6.0
            elif len(term) >= 7:
                weight = 2.5
            elif len(term) >= 5:
                weight = 1.5
            else:
                weight = 1.0
            overlap += weight * min(query_count, term_count)
        coverage = overlap / math.sqrt(sum(query_terms.values()) * sum(text_terms.values()))
        text_normalized = text.lower().replace("ё", "е")
        phrase_bonus = 0.0
        phrase_terms = [_normalize_token(token) for token in _TOKEN_RE.findall(query)]
        for start in range(0, max(0, len(phrase_terms) - 1)):
            phrase = " ".join(phrase_terms[start : start + 2])
            if len(phrase) >= 7 and phrase in text_normalized:
                phrase_bonus += 0.35
        number_bonus = 0.5 * len(query_numbers & set(text_terms))
        return coverage + phrase_bonus + number_bonus

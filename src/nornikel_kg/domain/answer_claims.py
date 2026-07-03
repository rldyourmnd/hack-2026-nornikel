from __future__ import annotations

import re

from nornikel_kg.domain.models import AnswerSentence, AnswerVerification, EvidenceSpan
from nornikel_kg.domain.security import SourceLabelPolicy

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _normalize_number(token: str) -> str:
    normalized = token.replace(",", ".")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _numbers_in(text: str) -> set[str]:
    return {_normalize_number(match) for match in _NUMBER_RE.findall(text)}


def sentence_numbers_supported(sentence: str, cited_texts: list[str]) -> bool:
    """Every number in the sentence must literally exist in the cited spans.

    A citation-existence gate alone lets a model write «твердость 999 HV» and
    cite a real span (audit H1); numbers are where fabrication hurts most, so
    they are checked against the evidence text itself.
    """
    sentence_numbers = _numbers_in(sentence)
    if not sentence_numbers:
        return True
    evidence_numbers: set[str] = set()
    for text in cited_texts:
        evidence_numbers.update(_numbers_in(text))
    return sentence_numbers.issubset(evidence_numbers)


_CONTENT_WORD_RE = re.compile(r"[a-zа-яё]{4,}")
_NEGATION_CUES = frozenset({"не", "нет", "без", "ни", "нельзя", "no", "not", "never"})
_STOPWORDS = frozenset(
    {
        "быть", "были", "было", "если", "также", "чтобы", "этот", "эта", "эти",
        "который", "которые", "when", "with", "that", "this", "from", "have",
        "were", "which",
    }
)


def _content_words(text: str) -> list[str]:
    normalized = text.lower().replace("ё", "е")
    return [word for word in _CONTENT_WORD_RE.findall(normalized) if word not in _STOPWORDS]


def _has_negation(text: str) -> bool:
    tokens = set(re.findall(r"[a-zа-яё]+", text.lower().replace("ё", "е")))
    return bool(tokens & _NEGATION_CUES)


def sentence_semantically_supported(sentence: str, cited_texts: list[str]) -> bool:
    """Rule-based semantic support (CI-safe, no NLI model).

    Cited spans must cover most of the sentence's content words (prefix-based
    containment tolerates Russian morphology) and must not flip its polarity —
    a negation the sentence introduces but no cited span carries («не превышает
    5 %» vs «превышает 5 %») counts as unsupported.
    """
    words = _content_words(sentence)
    if not words:
        return True
    corpus_words = [
        word
        for text in cited_texts
        for word in _CONTENT_WORD_RE.findall(text.lower().replace("ё", "е"))
    ]
    corpus_prefixes = {word[:5] for word in corpus_words}
    covered = sum(1 for word in words if word[:5] in corpus_prefixes)
    if covered / len(words) < 0.6:
        return False
    # A negation the sentence introduces but no cited span carries flips meaning.
    introduces_negation = _has_negation(sentence) and not any(
        _has_negation(text) for text in cited_texts
    )
    return not introduces_negation


class ClaimVerifier:
    def verify(
        self,
        *,
        answer_summary: list[AnswerSentence],
        evidence_spans: list[EvidenceSpan],
        source_label_policy: SourceLabelPolicy,
        fact_number_text: str = "",
    ) -> AnswerVerification:
        supported = [sentence for sentence in answer_summary if sentence.supporting_span_ids]
        unsupported_claim_count = len(answer_summary) - len(supported)
        citation_coverage = 1.0 if not answer_summary else len(supported) / len(answer_summary)

        span_by_id = {span.span_id: span for span in evidence_spans}
        # Ledger-derived numbers (Δ, regime values) legitimately appear in
        # fact-backed sentences without being in the span text.
        fact_numbers = _numbers_in(fact_number_text)
        source_label_leak_count = 0
        numeric_mismatch_count = 0
        semantic_unsupported_count = 0
        for sentence in answer_summary:
            for span_id in sentence.supporting_span_ids:
                span = span_by_id.get(span_id)
                if span is None or not source_label_policy.is_allowed(span):
                    source_label_leak_count += 1
            cited_texts = [
                span_by_id[span_id].visible_text
                for span_id in sentence.supporting_span_ids
                if span_id in span_by_id
            ]
            if not cited_texts:
                continue
            # Numeric support: every number in the sentence must appear in a
            # cited span (fact-backed sentences may also use ledger fact numbers).
            supported_numbers: set[str] = set()
            for text in cited_texts:
                supported_numbers |= _numbers_in(text)
            if sentence.supporting_fact_ids:
                supported_numbers |= fact_numbers
            if _numbers_in(sentence.sentence) - supported_numbers:
                numeric_mismatch_count += 1
            # Semantic support: content-word overlap + negation parity.
            if not sentence_semantically_supported(sentence.sentence, cited_texts):
                semantic_unsupported_count += 1

        return AnswerVerification(
            citation_coverage=citation_coverage,
            unsupported_claim_count=unsupported_claim_count,
            source_label_leak_count=source_label_leak_count,
            numeric_mismatch_count=numeric_mismatch_count,
            semantic_unsupported_count=semantic_unsupported_count,
        )

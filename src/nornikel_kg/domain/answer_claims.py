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


class ClaimVerifier:
    def verify(
        self,
        *,
        answer_summary: list[AnswerSentence],
        evidence_spans: list[EvidenceSpan],
        source_label_policy: SourceLabelPolicy,
    ) -> AnswerVerification:
        supported = [sentence for sentence in answer_summary if sentence.supporting_span_ids]
        unsupported_claim_count = len(answer_summary) - len(supported)
        citation_coverage = 1.0 if not answer_summary else len(supported) / len(answer_summary)

        span_by_id = {span.span_id: span for span in evidence_spans}
        source_label_leak_count = 0
        numeric_mismatch_count = 0
        for sentence in answer_summary:
            for span_id in sentence.supporting_span_ids:
                span = span_by_id.get(span_id)
                if span is None or not source_label_policy.is_allowed(span):
                    source_label_leak_count += 1
            if sentence.supporting_fact_ids:
                # Fact-backed sentences (deterministic assembler) derive
                # numbers like Δ from structured ledger measurements — their
                # provenance is the fact id, not the literal span text.
                continue
            cited_texts = [
                span_by_id[span_id].visible_text
                for span_id in sentence.supporting_span_ids
                if span_id in span_by_id
            ]
            if cited_texts and not sentence_numbers_supported(sentence.sentence, cited_texts):
                numeric_mismatch_count += 1

        return AnswerVerification(
            citation_coverage=citation_coverage,
            unsupported_claim_count=unsupported_claim_count,
            source_label_leak_count=source_label_leak_count,
            numeric_mismatch_count=numeric_mismatch_count,
        )

from __future__ import annotations

from nornikel_kg.domain.answer_claims import ClaimVerifier
from nornikel_kg.domain.evidence import EvidenceSpanFactory
from nornikel_kg.domain.models import AnswerSentence, EvidenceSpan
from nornikel_kg.domain.security import SourceLabelPolicy


def test_claim_verifier_rejects_unsupported_sentence() -> None:
    verifier = ClaimVerifier()
    verification = verifier.verify(
        answer_summary=[AnswerSentence(sentence="Unsupported", supporting_span_ids=[])],
        evidence_spans=[],
        source_label_policy=SourceLabelPolicy(),
    )
    assert verification.unsupported_claim_count == 1
    assert verification.citation_coverage == 0.0


def test_claim_verifier_counts_source_label_leaks() -> None:
    span = EvidenceSpanFactory().create(
        source_id="src_test",
        artifact_type="text",
        parser_profile="test",
        artifact_locator="doc.md",
        span_type="text",
        visible_text="restricted evidence",
        stable_locator="block_1",
        security_label="restricted",
    )
    verification = ClaimVerifier().verify(
        answer_summary=[
            AnswerSentence(sentence="Uses restricted span", supporting_span_ids=[span.span_id])
        ],
        evidence_spans=[span],
        source_label_policy=SourceLabelPolicy(allowed_labels=frozenset({"public"})),
    )
    assert verification.source_label_leak_count == 1


def _span(text: str) -> EvidenceSpan:
    return EvidenceSpanFactory().create(
        source_id="src_sem",
        artifact_type="text",
        parser_profile="test",
        artifact_locator="doc.md",
        span_type="text",
        visible_text=text,
        stable_locator="block_1",
        security_label="internal",
    )


def test_claim_verifier_flags_negation_flip() -> None:
    span = _span("Содержание меди превышает пять процентов в концентрате.")
    verification = ClaimVerifier().verify(
        answer_summary=[
            AnswerSentence(
                sentence="Содержание меди не превышает пять процентов в концентрате.",
                supporting_span_ids=[span.span_id],
            )
        ],
        evidence_spans=[span],
        source_label_policy=SourceLabelPolicy(),
    )
    assert verification.semantic_unsupported_count == 1


def test_claim_verifier_accepts_semantically_supported_sentence() -> None:
    span = _span("Содержание меди превышает пять процентов в концентрате.")
    verification = ClaimVerifier().verify(
        answer_summary=[
            AnswerSentence(
                sentence="Содержание меди превышает пять процентов.",
                supporting_span_ids=[span.span_id],
            )
        ],
        evidence_spans=[span],
        source_label_policy=SourceLabelPolicy(),
    )
    assert verification.semantic_unsupported_count == 0

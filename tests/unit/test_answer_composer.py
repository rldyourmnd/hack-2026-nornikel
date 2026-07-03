from __future__ import annotations

from nornikel_kg.adapters.llm import FakeLLM
from nornikel_kg.domain.models import AnswerSentence, EvidenceSpan
from nornikel_kg.services.answer_composer import LLMAnswerComposer


def _span(span_id: str, text: str = "Ni-30Cu 245 HV") -> EvidenceSpan:
    return EvidenceSpan(
        span_id=span_id,
        source_id="src_x",
        artifact_id="art_x",
        span_type="text",
        visible_text=text,
        page=1,
        locator={"stable_locator": "block_1"},
        validation_status="validated_rule",
        evidence_confidence=0.97,
        security_label="internal",
    )


def _fallback() -> list[AnswerSentence]:
    return [AnswerSentence(sentence="Детерминированный ответ.", supporting_span_ids=["evs_1"])]


def test_valid_llm_answer_is_used() -> None:
    fake = FakeLLM(
        canned={
            "answer": {
                "sentences": [
                    {
                        "sentence": "Твердость Ni-30Cu выросла до 245 HV.",
                        "supporting_span_ids": ["evs_1"],
                    }
                ]
            }
        }
    )
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Что с твердостью?",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_1",
    )
    assert mode == "llm"
    assert summary[0].sentence.startswith("Твердость")
    assert summary[0].supporting_span_ids == ["evs_1"]


def test_unsupported_sentences_trigger_regeneration_then_fallback() -> None:
    fake = FakeLLM()
    # Both attempts cite a span that is NOT in the packet.
    fake.queue_response(
        {"sentences": [{"sentence": "Выдумка.", "supporting_span_ids": ["evs_fake"]}]}
    )
    fake.queue_response(
        {"sentences": [{"sentence": "Снова выдумка.", "supporting_span_ids": ["evs_fake"]}]}
    )
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Вопрос",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_2",
    )
    assert mode == "deterministic"
    assert summary == _fallback()
    assert len(fake.calls) == 2  # exactly one regeneration


def test_partial_validity_keeps_only_cited_sentences() -> None:
    fake = FakeLLM()
    fake.queue_response(
        {
            "sentences": [
                {"sentence": "Подтверждено.", "supporting_span_ids": ["evs_1"]},
                {"sentence": "Не подтверждено.", "supporting_span_ids": ["evs_missing"]},
            ]
        }
    )
    fake.queue_response(
        {
            "sentences": [
                {"sentence": "Подтверждено.", "supporting_span_ids": ["evs_1"]},
                {"sentence": "Опять мимо.", "supporting_span_ids": ["evs_missing"]},
            ]
        }
    )
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Вопрос",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_3",
    )
    assert mode == "llm"
    assert len(summary) == 1
    assert summary[0].supporting_span_ids == ["evs_1"]


def test_invalid_payload_falls_back_deterministically() -> None:
    fake = FakeLLM(canned={"answer": {"garbage": True}})
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Вопрос",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_4",
    )
    assert mode == "deterministic"
    assert summary == _fallback()

from __future__ import annotations

from nornikel_kg.adapters.llm import FakeLLM
from nornikel_kg.domain.models import AnswerSentence, EvidenceSpan
from nornikel_kg.ports.llm import LLMError, LLMResult
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


class _TransientLLMErrorThenSuccess:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, **kwargs: object) -> LLMResult:
        self.calls += 1
        if self.calls == 1:
            raise LLMError("empty completion")
        return LLMResult(
            content={
                "sentences": [
                    {
                        "sentence": "Твердость Ni-30Cu выросла до 245 HV.",
                        "supporting_span_ids": ["evs_1"],
                    }
                ]
            },
            model_id="fake-retry",
            latency_ms=0,
        )


def test_transient_llm_error_retries_before_fallback() -> None:
    fake = _TransientLLMErrorThenSuccess()
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Что с твердостью?",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_retry",
    )
    assert fake.calls == 2
    assert mode == "llm"
    assert summary[0].sentence.startswith("Твердость")


class _RaisingLLM:
    """An LLM adapter that raises a raw (non-LLMError) provider/transport error."""

    def generate_json(self, **kwargs: object) -> object:
        raise RuntimeError("raw provider/transport error")


def test_compose_falls_back_on_raw_provider_exception() -> None:
    """A raw provider exception (not LLMError) must yield the deterministic fallback,
    never propagate — otherwise it would 500 /qa/ask."""
    composer = LLMAnswerComposer(_RaisingLLM())  # type: ignore[arg-type]
    summary, mode = composer.compose(
        question="Вопрос",
        experiments=[],
        evidence=[_span("evs_1")],
        fallback_summary=_fallback(),
        run_id="run_raw",
    )
    assert mode == "deterministic"
    assert summary == _fallback()


def test_sentence_contradicts_cited_flags_direction_flip() -> None:
    from nornikel_kg.domain.answer_claims import sentence_contradicts_cited

    evidence = ["Продувка CO повышает потери никеля."]
    # opposite direction verb -> contradiction
    assert sentence_contradicts_cited("Продувка CO снижает потери никеля.", evidence) is True
    # same direction -> fine
    assert sentence_contradicts_cited("Продувка CO повышает потери никеля.", evidence) is False
    # number-heavy evidence with no direction words must NOT be flagged (no false drop)
    assert sentence_contradicts_cited("Твердость выросла до 245 HV.", ["Ni-30Cu 245 HV"]) is False


def test_compose_drops_direction_inverted_sentence() -> None:
    """An LLM sentence that inverts its cited evidence's direction is dropped, not
    shipped with a citation — falls back to the deterministic summary."""
    fake = FakeLLM()
    inverted = {
        "sentences": [
            {"sentence": "Продувка CO снижает потери никеля.", "supporting_span_ids": ["evs_1"]}
        ]
    }
    fake.queue_response(inverted)
    fake.queue_response(inverted)  # regeneration also inverted -> deterministic fallback
    composer = LLMAnswerComposer(fake)
    summary, mode = composer.compose(
        question="Вопрос",
        experiments=[],
        evidence=[_span("evs_1", text="Продувка CO повышает потери никеля.")],
        fallback_summary=_fallback(),
        run_id="run_dir",
    )
    assert mode == "deterministic"
    assert summary == _fallback()

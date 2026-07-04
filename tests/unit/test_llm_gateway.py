from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from nornikel_kg.adapters.llm import FakeLLM, LLMSettings, build_llm
from nornikel_kg.adapters.llm.gateway import LiteLLMGateway, TokenBudget
from nornikel_kg.ports.llm import LLMBudgetExceededError, LLMInvalidResponseError

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "nornikel_kg"

SCHEMA: dict[str, Any] = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _settings(**overrides: Any) -> LLMSettings:
    defaults: dict[str, Any] = {
        "llm_enabled": True,
        "llm_api_key": "test-key",
        "llm_extraction_model": "openai/test-extract",
        "llm_answer_model": "openai/test-answer",
    }
    defaults.update(overrides)
    return LLMSettings(**defaults)


def _completion_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def test_build_llm_returns_fake_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    adapter = build_llm()
    assert isinstance(adapter, FakeLLM)


def test_fake_llm_is_deterministic() -> None:
    fake = FakeLLM()
    first = fake.generate_json(
        task="extraction", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    second = fake.generate_json(
        task="extraction", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert first.content == second.content
    assert first.model_id == "fake-llm"


def test_fake_llm_queued_and_canned_responses() -> None:
    fake = FakeLLM(canned={"answer": {"sentences": []}})
    fake.queue_response({"queued": True})
    queued = fake.generate_json(
        task="answer", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    canned = fake.generate_json(
        task="answer", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert queued.content == {"queued": True}
    assert canned.content == {"sentences": []}
    assert len(fake.calls) == 2


def test_gateway_parses_json_and_charges_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = LiteLLMGateway(_settings())
    captured: dict[str, Any] = {}

    def stub_completion(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return _completion_response(json.dumps({"ok": True}))

    import litellm

    monkeypatch.setattr(litellm, "completion", stub_completion)
    result = gateway.generate_json(
        task="extraction",
        system_prompt="system",
        user_prompt="user",
        json_schema=SCHEMA,
        trace_id="run-1",
        tags=["ingest"],
    )
    assert result.content == {"ok": True}
    assert result.model_id == "openai/test-extract"
    assert result.input_tokens == 10 and result.output_tokens == 5
    assert gateway.budget.spent == 15
    assert captured["temperature"] == 0
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["metadata"]["trace_id"] == "run-1"
    assert "extraction" in captured["metadata"]["tags"]


def test_gateway_rejects_unrepairable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = LiteLLMGateway(_settings())
    import litellm

    monkeypatch.setattr(
        litellm, "completion", lambda **kwargs: _completion_response("plain prose, no JSON here")
    )
    with pytest.raises(LLMInvalidResponseError):
        gateway.generate_json(
            task="answer", system_prompt="s", user_prompt="u", json_schema=SCHEMA
        )


def test_gateway_repairs_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Weak models wrap JSON in markdown fences; the repair pass recovers it."""
    gateway = LiteLLMGateway(_settings())
    import litellm

    fenced = '```json\n{"sentences": [{"sentence": "ok", "supporting_span_ids": ["s1"]},]}\n```'
    monkeypatch.setattr(litellm, "completion", lambda **kwargs: _completion_response(fenced))
    result = gateway.generate_json(
        task="answer", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert result.content == {
        "sentences": [{"sentence": "ok", "supporting_span_ids": ["s1"]}]
    }


def test_token_budget_hard_stop() -> None:
    budget = TokenBudget(limit=20)
    budget.charge(15)
    with pytest.raises(LLMBudgetExceededError):
        budget.charge(10)


def test_missing_model_configuration_raises() -> None:
    settings = _settings(llm_extraction_model="")
    with pytest.raises(ValueError):
        settings.model_for("extraction")


def test_litellm_imported_only_inside_llm_adapter() -> None:
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if "adapters/llm" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        if "import litellm" in text or "from litellm" in text:
            offenders.append(path.as_posix())
    assert offenders == []


def test_strictify_adds_additional_properties() -> None:
    from nornikel_kg.adapters.llm.gateway import _strictify

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "object", "properties": {"x": {"type": "string"}}},
            }
        },
    }
    strict = _strictify(schema)
    assert strict["additionalProperties"] is False
    assert strict["properties"]["items"]["items"]["additionalProperties"] is False
    # original untouched
    assert "additionalProperties" not in schema


def test_gateway_retries_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 must back off and retry, not fail the call (shared folder quota)."""
    gateway = LiteLLMGateway(_settings())
    import litellm

    calls = {"n": 0}

    def flaky(**kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] < 3:
            raise litellm.RateLimitError(
                message="rate quota limit exceed", llm_provider="openai", model="m"
            )
        return _completion_response('{"sentences": []}')

    monkeypatch.setattr(litellm, "completion", flaky)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    result = gateway.generate_json(
        task="answer", system_prompt="s", user_prompt="u", json_schema=SCHEMA
    )
    assert calls["n"] == 3
    assert result.content == {"sentences": []}

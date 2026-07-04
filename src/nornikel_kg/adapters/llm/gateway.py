from __future__ import annotations

import itertools
import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

from nornikel_kg.adapters.llm.settings import LLMSettings
from nornikel_kg.adapters.ratelimit import get_limiter
from nornikel_kg.ports.llm import (
    LLMBudgetExceededError,
    LLMError,
    LLMInvalidResponseError,
    LLMResult,
    LLMTask,
)

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRIES = 6


def _strictify(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively enforce the OpenAI-compatible strict json_schema contract.

    Strict mode rejects object schemas where `additionalProperties` is unset
    OR where any `properties` key is missing from `required` — the second
    rule silently broke every extraction call until schemas were reviewed.
    Other providers ignore both fields.
    """
    result = dict(schema)
    if result.get("type") == "object":
        result.setdefault("additionalProperties", False)
        properties = result.get("properties")
        if isinstance(properties, dict):
            result["properties"] = {
                name: _strictify(value) if isinstance(value, dict) else value
                for name, value in properties.items()
            }
            result["required"] = list(properties.keys())
    if result.get("type") == "array" and isinstance(result.get("items"), dict):
        result["items"] = _strictify(result["items"])
    return result


@dataclass(frozen=True)
class _Provider:
    """One OpenAI-compatible LLM endpoint (used through LiteLLM)."""

    api_base: str
    api_key: str
    extraction_model: str
    answer_model: str

    def model_for(self, task: str) -> str:
        model = self.extraction_model if task == "extraction" else self.answer_model
        if not model:
            raise ValueError(f"No model configured for task '{task}' (check LLM_* env)")
        return model


def _build_providers(settings: LLMSettings) -> list[_Provider]:
    """Primary provider + an optional second one, round-robined for throughput."""
    providers = [
        _Provider(
            settings.llm_api_base,
            settings.llm_api_key,
            settings.llm_extraction_model,
            settings.llm_answer_model,
        )
    ]
    if settings.llm_api_base_2 and settings.llm_api_key_2 and settings.llm_model_2:
        providers.append(
            _Provider(
                settings.llm_api_base_2,
                settings.llm_api_key_2,
                settings.llm_model_2,
                settings.llm_model_2,
            )
        )
    return providers


def _provider_extra_headers(provider: _Provider) -> dict[str, str] | None:
    """Provider-specific OpenAI-compatible headers.

    Yandex AI Studio's OpenAI-compatible endpoint accepts the same request
    shape as OpenAI, but the folder must be forwarded as the OpenAI project.
    Keep this isolated so the main gateway call path stays identical across
    providers.
    """
    if "yandex" not in provider.api_base.lower():
        return None
    folder_id = os.getenv("YANDEX_FOLDER_ID", "").strip()
    return {"OpenAI-Project": folder_id} if folder_id else None


class TokenBudget:
    """Process-wide hard stop: once spent, every further LLM call raises."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._spent = 0
        self._lock = threading.Lock()

    @property
    def spent(self) -> int:
        return self._spent

    def charge(self, tokens: int) -> None:
        with self._lock:
            self._spent += tokens
            if self._spent > self.limit:
                logger.error("LLM token budget exceeded: %s > %s", self._spent, self.limit)
                raise LLMBudgetExceededError(
                    f"token budget exceeded: spent {self._spent} of {self.limit}"
                )


class LiteLLMGateway:
    """The only module allowed to touch litellm.

    Guided-JSON completions with temperature 0, request timeout, bounded retries,
    a concurrency cap protecting the stand, a hard token budget, and optional
    Langfuse success/failure callbacks (fire-and-forget, never blocking).
    """

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self._semaphore = threading.BoundedSemaphore(settings.llm_max_concurrency)
        self.budget = TokenBudget(settings.llm_token_budget)
        self._providers = _build_providers(settings)
        self._round_robin = itertools.count()
        self._configure_callbacks()

    def _configure_callbacks(self) -> None:
        if not self.settings.langfuse_configured:
            return
        import litellm

        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

    def generate_json(
        self,
        *,
        task: LLMTask,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        trace_id: str | None = None,
        tags: list[str] | None = None,
    ) -> LLMResult:
        import litellm

        json_schema = _strictify(json_schema)
        started = time.perf_counter()
        limiter = get_limiter("llm-completions", self.settings.llm_rps)
        providers = self._providers
        # Round-robin the starting provider across calls; a rate limit fails the
        # retry over to the next provider so both share the load.
        start = next(self._round_robin)
        provider = providers[start % len(providers)]
        model = provider.model_for(task)
        response: Any = None
        with self._semaphore:
            delay = 1.0
            for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
                provider = providers[(start + attempt - 1) % len(providers)]
                model = provider.model_for(task)
                limiter.acquire()
                try:
                    completion_kwargs: dict[str, Any] = {
                        "model": model,
                        "api_base": provider.api_base,
                        "api_key": provider.api_key,
                        "temperature": 0,
                        "timeout": self.settings.llm_timeout_s,
                        "num_retries": self.settings.llm_max_retries,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": task,
                                "schema": json_schema,
                                "strict": True,
                            },
                        },
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "metadata": {
                            "trace_id": trace_id,
                            "tags": [task, *(tags or [])],
                        },
                    }
                    extra_headers = _provider_extra_headers(provider)
                    if extra_headers is not None:
                        completion_kwargs["extra_headers"] = extra_headers
                    response = litellm.completion(**completion_kwargs)
                    break
                except Exception as error:
                    # Fail over to the next provider on ANY provider-side error
                    # (429, permission-denied, auth, 5xx, timeout) — the round-robin
                    # advances the deployment each attempt, so a dead primary
                    # (e.g. a revoked key) is covered by the secondary. Only give
                    # up once attempts are exhausted across providers.
                    if attempt == _RATE_LIMIT_RETRIES:
                        raise LLMError(
                            f"LLM call failed after {_RATE_LIMIT_RETRIES} attempts "
                            f"for task '{task}': {error}"
                        ) from error
                    logger.warning(
                        "LLM call on %s failed (%s); failover + retry in %.1fs",
                        model,
                        str(error)[:120],
                        delay,
                    )
                    time.sleep(delay + random.uniform(0, delay / 2))
                    delay = min(delay * 2, 20.0)
        if response is None:  # pragma: no cover - loop either breaks or raises
            raise LLMInvalidResponseError(f"no completion produced for task '{task}'")
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        output_tokens = getattr(usage, "completion_tokens", None) if usage else None
        self.budget.charge((input_tokens or 0) + (output_tokens or 0))

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise LLMInvalidResponseError(f"empty completion from {model} for task '{task}'")
        try:
            content = json.loads(raw_content)
        except json.JSONDecodeError:
            # Weak models wrap JSON in prose/markdown fences or drop commas;
            # a deterministic repair pass recovers most of them.
            import json_repair

            repaired = json_repair.repair_json(raw_content, return_objects=True)
            if not isinstance(repaired, dict):
                raise LLMInvalidResponseError(
                    f"non-JSON completion from {model} for task '{task}': {raw_content[:200]}"
                ) from None
            logger.info("Repaired malformed JSON completion for task '%s'", task)
            content = repaired
        if not isinstance(content, dict):
            raise LLMInvalidResponseError(
                f"JSON completion from {model} is not an object for task '{task}'"
            )

        return LLMResult(
            content=content,
            model_id=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata={"trace_id": trace_id, "tags": [task, *(tags or [])]},
        )

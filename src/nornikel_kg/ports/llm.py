from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

LLMTask = Literal["extraction", "answer"]


class LLMError(RuntimeError):
    """Base error for LLM gateway failures."""


class LLMInvalidResponseError(LLMError):
    """Raised when the model output cannot be parsed against the JSON contract."""


class LLMBudgetExceededError(LLMError):
    """Raised when the per-process token budget guard trips (hard stop)."""


@dataclass(frozen=True)
class LLMResult:
    content: dict[str, Any]
    model_id: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMPort(Protocol):
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
        """Run one guided-JSON completion for the given task and return parsed output."""

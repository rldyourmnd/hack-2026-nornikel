from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any

from nornikel_kg.ports.llm import LLMResult, LLMTask


class FakeLLM:
    """Deterministic LLM stand-in used whenever LLM_ENABLED=false.

    Outputs are either queued fixtures (tests) or a stable canned payload derived
    from the prompt hash, so pipelines behave identically across runs with no
    network or secrets.
    """

    def __init__(self, canned: dict[str, dict[str, Any]] | None = None) -> None:
        self._canned = canned or {}
        self._queued: deque[dict[str, Any]] = deque()
        self.calls: list[dict[str, Any]] = []

    def queue_response(self, content: dict[str, Any]) -> None:
        self._queued.append(content)

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
        self.calls.append(
            {
                "task": task,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "json_schema": json_schema,
                "trace_id": trace_id,
                "tags": tags or [],
            }
        )
        if self._queued:
            content = self._queued.popleft()
        elif task in self._canned:
            content = self._canned[task]
        else:
            digest = hashlib.sha256(
                json.dumps([task, user_prompt], ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            content = {"task": task, "deterministic_digest": digest[:16]}
        return LLMResult(
            content=content,
            model_id="fake-llm",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            metadata={"trace_id": trace_id, "tags": tags or []},
        )

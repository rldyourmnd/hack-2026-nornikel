from __future__ import annotations

from nornikel_kg.adapters.llm.fake import FakeLLM
from nornikel_kg.adapters.llm.settings import LLMSettings
from nornikel_kg.ports.llm import LLMPort


def build_llm(settings: LLMSettings | None = None) -> LLMPort:
    """Return the configured LLM adapter: LiteLLM gateway or the deterministic fake.

    LLM_ENABLED=false (the default, and the CI invariant) never imports litellm.
    """
    resolved = settings or LLMSettings()
    if not resolved.llm_enabled:
        return FakeLLM()
    from nornikel_kg.adapters.llm.gateway import LiteLLMGateway

    return LiteLLMGateway(resolved)


__all__ = ["FakeLLM", "LLMSettings", "build_llm"]

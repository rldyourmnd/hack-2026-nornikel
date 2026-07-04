from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Gateway configuration; every value comes from the environment matrix."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    llm_enabled: bool = False
    # Provider: Yandex AI Studio (OpenAI-compatible base), model
    # deepseek-4-flash, routed through LiteLLM. LLM_API_BASE / LLM_API_KEY are
    # the canonical env names; the legacy DATAEYES_* names still resolve during
    # the transition so an existing server .env keeps working.
    llm_api_base: str = Field(
        default="https://ai.api.cloud.yandex.net/v1",
        validation_alias=AliasChoices("LLM_API_BASE", "DATAEYES_API_BASE"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "DATAEYES_API_KEY"),
    )
    llm_extraction_model: str = ""
    llm_answer_model: str = ""
    llm_timeout_s: int = 30
    llm_max_retries: int = 1
    llm_max_concurrency: int = 3
    # Client-side pacing under the provider quota (Yandex: 10 concurrent
    # generations); paired with 429-aware backoff in the gateway.
    llm_rps: float = 5.0
    llm_token_budget: int = 500_000

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    def model_for(self, task: str) -> str:
        model = self.llm_extraction_model if task == "extraction" else self.llm_answer_model
        if not model:
            raise ValueError(f"No model configured for task '{task}' (check LLM_* env)")
        return model

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

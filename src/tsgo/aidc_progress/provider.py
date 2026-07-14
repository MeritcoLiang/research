"""Model/provider setup for the AIDC progress expert."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ..env import load_env_file


DEFAULT_AZURE_OPENAI_SCOPE = "https://ai.azure.com/.default"
DEFAULT_AZURE_OPENAI_BASE_PATH = "/openai/v1/"


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    provider: str
    model_name: str
    search_context_size: str
    max_turns: int
    tracing_disabled: bool

    @classmethod
    def from_env(
        cls,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        max_turns: int | None = None,
    ) -> "ProviderSettings":
        load_env_file()
        resolved_provider = (provider or os.getenv("AIDC_PROVIDER", "")).strip().casefold()
        if not resolved_provider:
            resolved_provider = "azure" if os.getenv("AZURE_OPENAI_ENDPOINT", "").strip() else "openai"
        if resolved_provider not in {"openai", "azure"}:
            raise RuntimeError("AIDC_PROVIDER 只能是 openai 或 azure。")

        if model_name:
            resolved_model = model_name.strip()
        elif resolved_provider == "azure":
            resolved_model = (
                os.getenv("AIDC_OPENAI_MODEL", "").strip()
                or os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
                or os.getenv("AZURE_OPENAI_MODEL", "").strip()
            )
        else:
            resolved_model = os.getenv("AIDC_OPENAI_MODEL", "gpt-5.4").strip()
        if not resolved_model:
            raise RuntimeError("缺少 AIDC_OPENAI_MODEL 或 AZURE_OPENAI_DEPLOYMENT。")

        context_size = os.getenv("AIDC_SEARCH_CONTEXT_SIZE", "high").strip().casefold()
        if context_size not in {"low", "medium", "high"}:
            raise RuntimeError("AIDC_SEARCH_CONTEXT_SIZE 只能是 low、medium 或 high。")

        resolved_turns = max_turns or int(os.getenv("AIDC_MAX_TURNS", "30"))
        if resolved_turns < 2:
            raise RuntimeError("AIDC_MAX_TURNS 必须至少为 2。")

        return cls(
            provider=resolved_provider,
            model_name=resolved_model,
            search_context_size=context_size,
            max_turns=resolved_turns,
            tracing_disabled=_env_bool("AIDC_DISABLE_TRACING", default=True),
        )


def build_agent_model(settings: ProviderSettings) -> Any:
    """Return an Agents SDK model name or an Azure-backed Responses model."""

    _configure_tracing(settings.tracing_disabled)
    if settings.provider == "openai":
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise RuntimeError("AIDC_PROVIDER=openai 时必须设置 OPENAI_API_KEY。")
        return settings.model_name
    return _build_azure_responses_model(settings.model_name)


def _build_azure_responses_model(deployment: str) -> Any:
    load_env_file()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("AIDC_PROVIDER=azure 时必须设置 AZURE_OPENAI_ENDPOINT。")
    try:
        from agents.models.openai_responses import OpenAIResponsesModel
        from azure.identity import AzureCliCredential, get_bearer_token_provider
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("AIDC Agent 需要安装：pip install -e '.[aidc]'") from exc

    scope = os.getenv("AZURE_OPENAI_TOKEN_SCOPE", DEFAULT_AZURE_OPENAI_SCOPE)
    timeout = float(os.getenv("AZURE_OPENAI_TIMEOUT", "180"))
    credential = AzureCliCredential()
    token_provider = get_bearer_token_provider(credential, scope)
    client = AsyncOpenAI(
        base_url=normalize_azure_openai_base_url(endpoint),
        api_key=token_provider(),
        timeout=timeout,
    )
    return OpenAIResponsesModel(model=deployment, openai_client=client)


def normalize_azure_openai_base_url(endpoint: str) -> str:
    cleaned = endpoint.strip().rstrip("/")
    if cleaned.endswith("/openai/v1"):
        return f"{cleaned}/"
    if cleaned.endswith("/openai"):
        return f"{cleaned}/v1/"
    return f"{cleaned}{DEFAULT_AZURE_OPENAI_BASE_PATH}"


def _configure_tracing(disabled: bool) -> None:
    try:
        from agents import set_tracing_disabled
    except ImportError as exc:
        raise RuntimeError("AIDC Agent 需要安装：pip install -e '.[aidc]'") from exc
    set_tracing_disabled(disabled)


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} 必须是 true/false、1/0、yes/no 或 on/off。")

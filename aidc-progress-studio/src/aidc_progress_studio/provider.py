from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from dotenv import find_dotenv, load_dotenv

from .models import RuntimeOptions

DEFAULT_SCOPE = "https://ai.azure.com/.default"


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    provider: Literal["azure", "openai"]
    model: str
    search_context_size: Literal["low", "medium", "high"]
    max_turns: int
    tracing_disabled: bool

    @classmethod
    def resolve(cls, runtime: RuntimeOptions) -> "ProviderSettings":
        load_environment()
        provider = runtime.provider
        if runtime.model and runtime.model.strip():
            model = runtime.model.strip()
        elif provider == "azure":
            model = (
                os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
                or os.getenv("AIDC_OPENAI_MODEL", "").strip()
            )
        else:
            model = os.getenv("AIDC_OPENAI_MODEL", "gpt-5.4").strip()
        if not model:
            raise RuntimeError("缺少模型名称：请设置 AZURE_OPENAI_DEPLOYMENT 或 AIDC_OPENAI_MODEL。")
        return cls(
            provider=provider,
            model=model,
            search_context_size=runtime.search_context_size,
            max_turns=runtime.max_turns,
            tracing_disabled=_env_bool("AIDC_DISABLE_TRACING", True),
        )


def load_environment() -> None:
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file, override=False)


def build_model(settings: ProviderSettings) -> Any:
    _configure_tracing(settings.tracing_disabled)
    if settings.provider == "openai":
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise RuntimeError("OpenAI 模式需要在 .env 中设置 OPENAI_API_KEY。")
        return settings.model
    return _build_azure_model(settings.model)


def _build_azure_model(deployment: str) -> Any:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("Azure 模式需要在 .env 中设置 AZURE_OPENAI_ENDPOINT。")

    try:
        from agents.models.openai_responses import OpenAIResponsesModel
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("缺少 Agents SDK：pip install -e .") from exc

    timeout = float(os.getenv("AZURE_OPENAI_TIMEOUT", "180"))
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    if api_key:
        credential: str | Any = api_key
    else:
        try:
            from azure.identity import AzureCliCredential, get_bearer_token_provider
        except ImportError as exc:
            raise RuntimeError("Azure 登录模式需要 azure-identity；请重新安装工程。") from exc
        scope = os.getenv("AZURE_OPENAI_TOKEN_SCOPE", DEFAULT_SCOPE).strip() or DEFAULT_SCOPE
        credential = get_bearer_token_provider(AzureCliCredential(), scope)

    client = AsyncOpenAI(
        base_url=normalize_azure_base_url(endpoint),
        api_key=credential,
        timeout=timeout,
    )
    return OpenAIResponsesModel(model=deployment, openai_client=client)


def normalize_azure_base_url(endpoint: str) -> str:
    cleaned = endpoint.strip().rstrip("/")
    if cleaned.endswith("/openai/v1"):
        return f"{cleaned}/"
    if cleaned.endswith("/openai"):
        return f"{cleaned}/v1/"
    return f"{cleaned}/openai/v1/"


def _configure_tracing(disabled: bool) -> None:
    try:
        from agents import set_tracing_disabled
    except ImportError as exc:
        raise RuntimeError("缺少 Agents SDK：pip install -e .") from exc
    set_tracing_disabled(disabled)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} 必须是 true/false、1/0、yes/no 或 on/off。")

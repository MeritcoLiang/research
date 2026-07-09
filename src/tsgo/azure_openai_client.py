"""Azure OpenAI ModelClient using `az login`.

This client is intentionally small: it only implements the existing
`ModelClient.generate(prompt) -> str` contract so LLM Operators can make real
Azure OpenAI calls without introducing a new execution semantic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .env import load_env_file


DEFAULT_AZURE_OPENAI_SCOPE = "https://ai.azure.com/.default"
DEFAULT_AZURE_OPENAI_BASE_PATH = "/openai/v1/"


@dataclass(slots=True)
class AzureOpenAIResponsesModelClient:
    """Azure OpenAI Responses API client authenticated through Azure CLI.

    Required runtime setup:

    - `az login`
    - user has a role such as Cognitive Services OpenAI User on the resource
    - `AZURE_OPENAI_ENDPOINT`, for example `https://<resource>.openai.azure.com`
    - `AZURE_OPENAI_DEPLOYMENT`, the Azure deployment name to call

    The implementation uses the OpenAI Python client against Azure's `/openai/v1/`
    endpoint and refreshes the Entra token before every request.
    """

    endpoint: str
    deployment: str
    system_message: str = "你是 Thought-State Graph Orchestration Engine 中的 Operator。必须严格遵守请求的结构化输出约束。"
    temperature: float | None = 0.2
    max_output_tokens: int | None = 2048
    token_scope: str = DEFAULT_AZURE_OPENAI_SCOPE
    timeout: float | None = 90.0
    prompts: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "AzureOpenAIResponsesModelClient":
        load_env_file()
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        deployment = (
            os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
            or os.getenv("AZURE_OPENAI_MODEL", "").strip()
        )
        if not endpoint:
            raise RuntimeError("缺少环境变量 AZURE_OPENAI_ENDPOINT。")
        if not deployment:
            raise RuntimeError("缺少环境变量 AZURE_OPENAI_DEPLOYMENT。")
        return cls(
            endpoint=endpoint,
            deployment=deployment,
            system_message=os.getenv(
                "AZURE_OPENAI_SYSTEM_MESSAGE",
                "你是 Thought-State Graph Orchestration Engine 中的 Operator。必须严格遵守请求的结构化输出约束。",
            ),
            temperature=_optional_float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.2")),
            max_output_tokens=_optional_int(os.getenv("AZURE_OPENAI_MAX_OUTPUT_TOKENS", "2048")),
            token_scope=os.getenv("AZURE_OPENAI_TOKEN_SCOPE", DEFAULT_AZURE_OPENAI_SCOPE),
            timeout=_optional_float(os.getenv("AZURE_OPENAI_TIMEOUT", "90")),
        )

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        client = self._client()
        request: dict[str, Any] = {
            "model": self.deployment,
            "input": f"{self.system_message}\n\n{prompt}",
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.max_output_tokens is not None:
            request["max_output_tokens"] = self.max_output_tokens
        response = client.responses.create(**request)
        text = getattr(response, "output_text", None)
        if text:
            return str(text)
        return _extract_output_text(response)

    def _client(self) -> Any:
        try:
            from azure.identity import AzureCliCredential, get_bearer_token_provider
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Azure OpenAI 调用需要安装：pip install -e '.[azure]'") from exc

        credential = AzureCliCredential()
        token_provider = get_bearer_token_provider(credential, self.token_scope)
        return OpenAI(
            base_url=_normalize_azure_openai_base_url(self.endpoint),
            api_key=token_provider(),
            timeout=self.timeout,
        )


def _normalize_azure_openai_base_url(endpoint: str) -> str:
    cleaned = endpoint.strip().rstrip("/")
    if cleaned.endswith("/openai/v1"):
        return f"{cleaned}/"
    if cleaned.endswith("/openai"):
        return f"{cleaned}/v1/"
    return f"{cleaned}{DEFAULT_AZURE_OPENAI_BASE_PATH}"


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def _extract_output_text(response: Any) -> str:
    try:
        output = getattr(response, "output", []) or []
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None) or []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts)
    except Exception:
        pass
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json(indent=2)
    return str(response)

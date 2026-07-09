"""DeepSeek ModelClient using its OpenAI-compatible API.

DeepSeek is implemented as an Operator implementation detail through the
existing `ModelClient.generate(prompt) -> str` contract. No provider router or
backend semantic is introduced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .env import load_env_file


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"


@dataclass(slots=True)
class DeepSeekOpenAIChatModelClient:
    """DeepSeek client using the OpenAI-compatible Chat Completions API."""

    api_key: str
    model: str = DEFAULT_DEEPSEEK_MODEL
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    system_message: str = "你是 Thought-State Graph Orchestration Engine 中的 Operator。必须严格遵守请求的结构化输出约束。"
    temperature: float | None = 0.2
    max_tokens: int | None = 2048
    reasoning_effort: str | None = "high"
    thinking: str | None = "enabled"
    timeout: float | None = 90.0
    prompts: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "DeepSeekOpenAIChatModelClient":
        load_env_file()
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY。")
        return cls(
            api_key=api_key,
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL,
            base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip() or DEFAULT_DEEPSEEK_BASE_URL,
            system_message=os.getenv(
                "DEEPSEEK_SYSTEM_MESSAGE",
                "你是 Thought-State Graph Orchestration Engine 中的 Operator。必须严格遵守请求的结构化输出约束。",
            ),
            temperature=_optional_float(os.getenv("DEEPSEEK_TEMPERATURE", "0.2")),
            max_tokens=_optional_int(os.getenv("DEEPSEEK_MAX_TOKENS", "2048")),
            reasoning_effort=_optional_str(os.getenv("DEEPSEEK_REASONING_EFFORT", "high")),
            thinking=_optional_str(os.getenv("DEEPSEEK_THINKING", "enabled")),
            timeout=_optional_float(os.getenv("DEEPSEEK_TIMEOUT", "90")),
        )

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        client = self._client()
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature
        if self.max_tokens is not None:
            request["max_tokens"] = self.max_tokens
        if self.reasoning_effort:
            request["reasoning_effort"] = self.reasoning_effort
        if self.thinking:
            request["extra_body"] = {"thinking": {"type": self.thinking}}

        response = client.chat.completions.create(**request)
        content = response.choices[0].message.content
        if content:
            return str(content)
        if hasattr(response, "model_dump_json"):
            return response.model_dump_json(indent=2)
        return str(response)

    def _client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("DeepSeek 调用需要安装：pip install -e '.[deepseek]'") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)


def _optional_str(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)

from __future__ import annotations

import pytest

from tsgo.deepseek_client import DeepSeekOpenAIChatModelClient


def test_deepseek_client_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        DeepSeekOpenAIChatModelClient.from_env()


def test_deepseek_client_from_env_reads_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_TEMPERATURE", "")
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "")
    monkeypatch.setenv("DEEPSEEK_REASONING_EFFORT", "")
    monkeypatch.setenv("DEEPSEEK_THINKING", "")

    client = DeepSeekOpenAIChatModelClient.from_env()

    assert client.api_key == "test-key"
    assert client.model == "deepseek-v4-flash"
    assert client.base_url == "https://api.deepseek.com"
    assert client.temperature is None
    assert client.max_tokens is None
    assert client.reasoning_effort is None
    assert client.thinking is None

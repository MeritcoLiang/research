from __future__ import annotations

import pytest

from tsgo.azure_openai_client import AzureOpenAIResponsesModelClient, _normalize_azure_openai_base_url


def test_normalize_azure_openai_base_url() -> None:
    assert (
        _normalize_azure_openai_base_url("https://example.openai.azure.com")
        == "https://example.openai.azure.com/openai/v1/"
    )
    assert (
        _normalize_azure_openai_base_url("https://example.openai.azure.com/openai")
        == "https://example.openai.azure.com/openai/v1/"
    )
    assert (
        _normalize_azure_openai_base_url("https://example.openai.azure.com/openai/v1")
        == "https://example.openai.azure.com/openai/v1/"
    )


def test_azure_client_from_env_requires_endpoint_and_deployment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        AzureOpenAIResponsesModelClient.from_env()

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_DEPLOYMENT"):
        AzureOpenAIResponsesModelClient.from_env()


def test_azure_client_from_env_reads_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-prod")
    monkeypatch.setenv("AZURE_OPENAI_TEMPERATURE", "")
    monkeypatch.setenv("AZURE_OPENAI_MAX_OUTPUT_TOKENS", "")

    client = AzureOpenAIResponsesModelClient.from_env()

    assert client.endpoint == "https://example.openai.azure.com"
    assert client.deployment == "gpt-4o-prod"
    assert client.temperature is None
    assert client.max_output_tokens is None

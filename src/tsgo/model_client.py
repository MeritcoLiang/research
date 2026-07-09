"""Model client contracts for LLM Operators.

`ModelClient` is a minimal helper used inside LLM Operators. It is not a new
Thought-State Graph execution semantic; Operator remains the only execution
semantic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


class ModelClient(Protocol):
    """Minimal model interface used inside LLM Operators."""

    def generate(self, prompt: str) -> str:
        """Return raw model text for a prompt."""


@dataclass(slots=True)
class EchoModelClient:
    """A deterministic placeholder client used by tests and demos."""

    prefix: str = "MOCK_MODEL_OUTPUT"

    def generate(self, prompt: str) -> str:
        escaped = prompt.replace("\n", " ")[:500]
        return f"{self.prefix}: {escaped}"


@dataclass(slots=True)
class ScriptedModelClient:
    """Deterministic JSON-returning client for operator tests.

    Responses are consumed in order. Each prompt is recorded so tests can assert
    that an Operator actually called the model.
    """

    responses: list[str]
    prompts: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("ScriptedModelClient 没有剩余 responses。")
        return self.responses.pop(0)


@dataclass(slots=True)
class CallbackModelClient:
    """Deterministic client that computes responses from prompts."""

    callback: Callable[[str], str]
    prompts: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.callback(prompt)

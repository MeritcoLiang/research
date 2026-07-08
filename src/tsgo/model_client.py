"""Model client contracts for Pipeline v0.2.

v0.2 ships a deterministic mock client so the pipeline can run end-to-end
without requiring credentials or a production model provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ModelClient(Protocol):
    """Minimal model interface used by LLM-backed operators."""

    def generate(self, prompt: str) -> str:
        """Return raw model text for a prompt."""


@dataclass(slots=True)
class EchoModelClient:
    """A deterministic placeholder client used by tests and demos.

    Concrete mock operators do not depend on this client, but keeping the
    interface in v0.2 makes the boundary explicit for v0.3 LLM integration.
    """

    prefix: str = "MOCK_MODEL_OUTPUT"

    def generate(self, prompt: str) -> str:
        escaped = prompt.replace("\n", " ")[:500]
        return f"{self.prefix}: {escaped}"

"""Operator contracts for Pipeline v0.1.

An Operator is a deterministic wrapper around one stage of thought-state
transformation. Concrete implementations may call LLMs, tools, retrieval,
reward models, parsers, or hand-written validators, but the contract stays the
same: consume structured inputs and return structured outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .schema import ContextPacket, Rubric, Subtask, ThoughtState, Trace


@dataclass(slots=True)
class OperatorResult:
    """Standard result object returned by every operator."""

    new_states: list[ThoughtState] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


class Operator(ABC):
    """Base interface for all pipeline operators."""

    name: str

    @abstractmethod
    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        """Execute one stage transformation."""


class NotImplementedOperator(Operator):
    """Placeholder operator used while wiring the pipeline.

    This keeps the controller executable as a skeleton while making missing
    concrete implementations explicit.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        return OperatorResult(
            errors=[f"Operator '{self.name}' has not been implemented yet."],
            metadata={
                "operator": self.name,
                "expected_contract": "Return OperatorResult with new ThoughtState objects.",
            },
        )

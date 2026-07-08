"""Core state schema for Pipeline v0.1.

These dataclasses are deliberately model-client agnostic. They represent the
objects that move through the orchestration pipeline, regardless of whether a
future implementation uses a single LLM, multiple models, retrieval, tools,
reward models, or a graph search controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4


StageName = Literal[
    "root",
    "task_intake",
    "context_builder",
    "rubric_builder",
    "problem_decomposer",
    "candidate_generator",
    "thought_normalizer",
    "verifier_scorer",
    "improver",
    "aggregator",
    "final_validator",
    "trace_logger",
]

ClaimType = Literal[
    "fact",
    "reasoning",
    "recommendation",
    "assumption",
    "calculation",
    "code",
    "risk",
    "unknown",
]

TaskType = Literal[
    "research",
    "coding",
    "reasoning",
    "writing",
    "planning",
    "data",
    "decision",
    "system_design",
    "architecture",
    "mixed",
    "unknown",
]

Difficulty = Literal["low", "medium", "high", "frontier"]
StateStatus = Literal[
    "draft",
    "normalized",
    "scored",
    "improved",
    "aggregated",
    "validated",
    "rejected",
]


@dataclass(slots=True)
class Evidence:
    """A source, tool result, citation, test result, or user-provided artifact."""

    id: str
    kind: str
    content: str
    source: str | None = None
    reliability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolOutput:
    """Structured record of an external tool invocation."""

    id: str
    tool_name: str
    input: dict[str, Any]
    output: Any
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Claim:
    """An atomic claim extracted from a thought draft."""

    text: str
    claim_type: ClaimType = "unknown"
    confidence: float | None = None
    evidence_ids: list[str] = field(default_factory=list)
    verifier_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Score:
    """Multi-dimensional score used by the verifier/scorer stage."""

    correctness: float = 0.0
    completeness: float = 0.0
    relevance: float = 0.0
    clarity: float = 0.0
    groundedness: float = 0.0
    safety: float = 1.0
    novelty: float = 0.0
    actionability: float = 0.0
    overall: float = 0.0
    notes: list[str] = field(default_factory=list)

    def recompute_overall(self, weights: dict[str, float]) -> float:
        """Recompute the weighted overall score in-place and return it."""

        total_weight = sum(weights.values())
        if total_weight <= 0:
            self.overall = 0.0
            return self.overall

        weighted_sum = 0.0
        for key, weight in weights.items():
            weighted_sum += float(getattr(self, key, 0.0)) * weight
        self.overall = weighted_sum / total_weight
        return self.overall


@dataclass(slots=True)
class RubricItem:
    """One criterion in a task-specific rubric."""

    name: str
    weight: float
    description: str
    pass_threshold: float | None = None


@dataclass(slots=True)
class Rubric:
    """Task-specific objective function for scoring and aggregation."""

    items: list[RubricItem]
    hard_constraints: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)

    def weight_map(self) -> dict[str, float]:
        return {item.name: item.weight for item in self.items}


@dataclass(slots=True)
class TaskInfo:
    """Output of the task intake stage."""

    user_query: str
    task_type: TaskType = "unknown"
    difficulty: Difficulty = "medium"
    requires_tools: bool = False
    requires_citations: bool = False
    requires_computation: bool = False
    requires_user_context: bool = False
    answer_format: str = "structured_text"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ContextPacket:
    """Normalized context made available to downstream stages."""

    user_intent: str
    hard_constraints: list[str] = field(default_factory=list)
    soft_preferences: list[str] = field(default_factory=list)
    available_context: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    retrieved_evidence: list[Evidence] = field(default_factory=list)
    tool_plan: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Subtask:
    """A decomposed work unit that can be generated, verified, and aggregated."""

    id: str
    question: str
    task_type: TaskType = "unknown"
    required_outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ThoughtState:
    """The unit of orchestration.

    A ThoughtState may represent a raw candidate, a normalized candidate, a
    scored candidate, an improved candidate, an aggregated answer, or a final
    validated response.
    """

    id: str
    parent_ids: list[str]
    stage: StageName
    user_query: str

    task_type: TaskType = "unknown"
    draft: str | None = None
    summary: str | None = None

    claims: list[Claim] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    tool_outputs: list[ToolOutput] = field(default_factory=list)

    critique: list[str] = field(default_factory=list)
    score: Score | None = None
    uncertainty: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)

    status: StateStatus = "draft"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Trace:
    """Replayable record of a full pipeline run."""

    id: str
    user_query: str
    states: list[ThoughtState] = field(default_factory=list)
    task_info: TaskInfo | None = None
    context: ContextPacket | None = None
    rubric: Rubric | None = None
    subtasks: list[Subtask] = field(default_factory=list)
    final_state_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_state(self, state: ThoughtState) -> None:
        self.states.append(state)

    def add_states(self, states: list[ThoughtState]) -> None:
        self.states.extend(states)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_state_id(prefix: str = "state") -> str:
    """Create a compact unique state identifier."""

    return f"{prefix}_{uuid4().hex[:12]}"

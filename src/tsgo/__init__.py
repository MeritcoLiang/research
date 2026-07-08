"""Thought-State Graph Orchestration Engine package.

The v0.1 package is intentionally small: it defines structured state,
operator contracts, and a deterministic pipeline controller skeleton.
"""

from .schema import (
    Claim,
    ContextPacket,
    Evidence,
    Rubric,
    RubricItem,
    Score,
    StageName,
    Subtask,
    TaskInfo,
    ThoughtState,
    ToolOutput,
    Trace,
    new_state_id,
)
from .operators import Operator, OperatorResult
from .pipeline import PipelineConfig, PipelineController

__all__ = [
    "Claim",
    "ContextPacket",
    "Evidence",
    "Rubric",
    "RubricItem",
    "Score",
    "StageName",
    "Subtask",
    "TaskInfo",
    "ThoughtState",
    "ToolOutput",
    "Trace",
    "new_state_id",
    "Operator",
    "OperatorResult",
    "PipelineConfig",
    "PipelineController",
]

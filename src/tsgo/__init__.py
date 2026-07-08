"""Thought-State Graph Orchestration Engine package.

Pipeline v0.2 adds deterministic mock operators, a model-client boundary,
prompter contracts, JSON parsing helpers, trace sinks, and a runnable demo.
"""

from .demo import build_v02_controller, run_demo
from .mock_operators import build_mock_operators
from .model_client import EchoModelClient, ModelClient
from .operators import Operator, OperatorResult
from .parsing import JsonParseError, parse_json, parse_json_list, parse_json_object
from .pipeline import PipelineConfig, PipelineController
from .prompter import DefaultPipelinePrompter, Prompter
from .schema import (
    Claim,
    ClaimType,
    ContextPacket,
    Difficulty,
    Evidence,
    Rubric,
    RubricItem,
    Score,
    StageName,
    StateStatus,
    Subtask,
    TaskInfo,
    TaskType,
    ThoughtState,
    ToolOutput,
    Trace,
    new_state_id,
)
from .trace_store import JsonTraceSink, JsonlTraceSink, TraceSink

__all__ = [
    "Claim",
    "ClaimType",
    "ContextPacket",
    "Difficulty",
    "Evidence",
    "Rubric",
    "RubricItem",
    "Score",
    "StageName",
    "StateStatus",
    "Subtask",
    "TaskInfo",
    "TaskType",
    "ThoughtState",
    "ToolOutput",
    "Trace",
    "new_state_id",
    "Operator",
    "OperatorResult",
    "PipelineConfig",
    "PipelineController",
    "Prompter",
    "DefaultPipelinePrompter",
    "ModelClient",
    "EchoModelClient",
    "TraceSink",
    "JsonlTraceSink",
    "JsonTraceSink",
    "JsonParseError",
    "parse_json",
    "parse_json_list",
    "parse_json_object",
    "build_mock_operators",
    "build_v02_controller",
    "run_demo",
]

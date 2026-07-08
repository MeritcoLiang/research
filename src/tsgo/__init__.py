"""Thought-State Graph Orchestration Engine package.

Pipeline v0.2 exposes a shared runtime, event stream primitives, graph adapters,
prompter contracts, JSON parsing helpers, trace sinks, and deterministic mock
operators.
"""

from .events import EventSink, InMemoryEventSink, NoopEventSink, TraceEvent
from .graph import GraphEdge, GraphNode, GraphSnapshot, event_to_graph_delta, trace_to_graph
from .mock_operators import build_mock_operators
from .model_client import EchoModelClient, ModelClient
from .operators import Operator, OperatorResult
from .parsing import JsonParseError, parse_json, parse_json_list, parse_json_object
from .pipeline import PipelineConfig, PipelineController
from .prompter import DefaultPipelinePrompter, Prompter
from .runtime import DEFAULT_QUERY, build_v02_controller, run_pipeline_message
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
    "DEFAULT_QUERY",
    "build_v02_controller",
    "run_pipeline_message",
    "TraceEvent",
    "EventSink",
    "NoopEventSink",
    "InMemoryEventSink",
    "GraphNode",
    "GraphEdge",
    "GraphSnapshot",
    "trace_to_graph",
    "event_to_graph_delta",
]

"""Thought-State Graph Orchestration Engine package.

Pipeline v0.3 adds LLM-backed operators and structured JSON contracts while
preserving the v0.2 runtime, event stream, graph, and trace interfaces.
"""

from .events import EventSink, InMemoryEventSink, NoopEventSink, TraceEvent
from .graph import GraphEdge, GraphNode, GraphSnapshot, event_to_graph_delta, trace_to_graph
from .json_contracts import (
    parse_aggregate_packet,
    parse_generate_packet,
    parse_improve_packet,
    parse_normalize_packet,
    parse_score_packets,
    parse_validation_packet,
)
from .llm_operators import build_llm_operators
from .mock_operators import build_mock_operators
from .model_client import CallbackModelClient, EchoModelClient, ModelClient, ScriptedModelClient
from .operators import Operator, OperatorResult
from .parsing import JsonParseError, parse_json, parse_json_list, parse_json_object
from .pipeline import PipelineConfig, PipelineController
from .prompter import DefaultPipelinePrompter, Prompter
from .runtime import (
    DEFAULT_QUERY,
    DEFAULT_V03_QUERY,
    build_v02_controller,
    build_v03_controller,
    run_llm_pipeline_message,
    run_pipeline_message,
)
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
    "ScriptedModelClient",
    "CallbackModelClient",
    "TraceSink",
    "JsonlTraceSink",
    "JsonTraceSink",
    "JsonParseError",
    "parse_json",
    "parse_json_list",
    "parse_json_object",
    "parse_generate_packet",
    "parse_normalize_packet",
    "parse_score_packets",
    "parse_improve_packet",
    "parse_aggregate_packet",
    "parse_validation_packet",
    "build_mock_operators",
    "build_llm_operators",
    "DEFAULT_QUERY",
    "DEFAULT_V03_QUERY",
    "build_v02_controller",
    "build_v03_controller",
    "run_pipeline_message",
    "run_llm_pipeline_message",
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

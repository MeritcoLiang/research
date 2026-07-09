"""Shared runtime entrypoints for CLI demos, tests, and Web UI.

v0.2 remains the deterministic Web UI path. v0.3 adds LLM-backed operators
behind the same PipelineController / Trace / EventSink contracts.
"""

from __future__ import annotations

from .events import EventSink
from .llm_operators import build_llm_operators
from .mock_operators import build_mock_operators
from .model_client import ModelClient
from .pipeline import PipelineConfig, PipelineController
from .prompter import DefaultPipelinePrompter, Prompter
from .schema import Trace


DEFAULT_QUERY = "进入 Pipeline v0.2：跑通 Prompter、mock runner、JSON parser 和 trace 持久化。"
DEFAULT_V03_QUERY = "进入 Pipeline v0.3：使用 LLM-backed operators 跑通结构化 JSON 合约。"


def build_v02_controller(
    *,
    trace_path: str = "traces/pipeline_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> PipelineController:
    """Create the deterministic Pipeline v0.2 controller."""

    config = PipelineConfig(
        default_num_branches=num_branches,
        max_improvement_rounds=1,
        top_k_for_aggregation=4,
        metadata={"trace_path": trace_path, "runner": "mock_v0.2"},
    )
    return PipelineController(
        operators=build_mock_operators(),
        config=config,
        event_sink=event_sink,
        session_id=session_id,
    )


def build_v03_controller(
    *,
    model_client: ModelClient,
    prompter: Prompter | None = None,
    trace_path: str = "traces/pipeline_v03_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> PipelineController:
    """Create the Pipeline v0.3 LLM-backed controller."""

    config = PipelineConfig(
        default_num_branches=num_branches,
        max_improvement_rounds=1,
        top_k_for_aggregation=max(4, num_branches),
        metadata={"trace_path": trace_path, "runner": "llm_v0.3"},
    )
    return PipelineController(
        operators=build_llm_operators(model_client=model_client, prompter=prompter or DefaultPipelinePrompter()),
        config=config,
        event_sink=event_sink,
        session_id=session_id,
    )


def run_pipeline_message(
    message: str = DEFAULT_QUERY,
    *,
    trace_path: str = "traces/pipeline_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> Trace:
    """Run one user message through the shared Pipeline v0.2 runtime."""

    controller = build_v02_controller(
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return controller.run(message)


def run_llm_pipeline_message(
    message: str = DEFAULT_V03_QUERY,
    *,
    model_client: ModelClient,
    prompter: Prompter | None = None,
    trace_path: str = "traces/pipeline_v03_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> Trace:
    """Run one user message through Pipeline v0.3 LLM-backed operators."""

    controller = build_v03_controller(
        model_client=model_client,
        prompter=prompter,
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return controller.run(message)

"""Shared runtime entrypoints for CLI demos, tests, Web UI, and graph engine.

v0.2 remains the generic deterministic path. v0.3 adds LLM Operators. The
SecondaryMarketAnalyst stage flow runs the documented 10 business stages and
emits realtime events for the Web UI.
"""

from __future__ import annotations

from .engine import GraphRunResult, run_controller_as_graph
from .events import EventSink
from .experts import build_secondary_market_operators
from .llm_operators import build_llm_operators
from .mock_operators import build_mock_operators
from .model_client import ModelClient
from .pipeline import PipelineConfig, PipelineController
from .prompter import DefaultPipelinePrompter, Prompter
from .schema import Trace


DEFAULT_QUERY = "进入 Pipeline v0.2：跑通 Prompter、mock runner、JSON parser 和 trace 持久化。"
DEFAULT_V03_QUERY = "进入 Pipeline v0.3：使用 LLM Operators 跑通结构化 JSON 合约。"
DEFAULT_SECONDARY_MARKET_QUERY = "请用二级市场分析师视角分析 AAPL 的中期机会和风险。"


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


def build_secondary_market_controller(
    *,
    trace_path: str = "traces/secondary_market_stage_flow.jsonl",
    num_branches: int = 6,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> PipelineController:
    """Create the runnable SecondaryMarketAnalyst 10-stage controller."""

    config = PipelineConfig(
        default_num_branches=num_branches,
        max_improvement_rounds=1,
        top_k_for_aggregation=12,
        metadata={
            "trace_path": trace_path,
            "runner": "secondary_market_stage_flow",
            "expert_profile": "SecondaryMarketAnalyst",
        },
    )
    return PipelineController(
        operators=build_secondary_market_operators(),
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
    """Create the Pipeline v0.3 LLM controller."""

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


def run_secondary_market_stage_flow(
    message: str = DEFAULT_SECONDARY_MARKET_QUERY,
    *,
    trace_path: str = "traces/secondary_market_stage_flow.jsonl",
    num_branches: int = 6,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> Trace:
    """Run the documented SecondaryMarketAnalyst 10-stage flow."""

    controller = build_secondary_market_controller(
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return controller.run(message)


def run_pipeline_graph(
    message: str = DEFAULT_QUERY,
    *,
    trace_path: str = "traces/pipeline_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> GraphRunResult:
    """Run v0.2 and return the canonical ThoughtGraph result."""

    controller = build_v02_controller(
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return run_controller_as_graph(controller, message)


def run_secondary_market_graph(
    message: str = DEFAULT_SECONDARY_MARKET_QUERY,
    *,
    trace_path: str = "traces/secondary_market_stage_flow.jsonl",
    num_branches: int = 6,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> GraphRunResult:
    """Run SecondaryMarketAnalyst stage flow and return ThoughtGraph."""

    controller = build_secondary_market_controller(
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return run_controller_as_graph(controller, message)


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
    """Run one user message through Pipeline v0.3 LLM Operators."""

    controller = build_v03_controller(
        model_client=model_client,
        prompter=prompter,
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return controller.run(message)


def run_llm_pipeline_graph(
    message: str = DEFAULT_V03_QUERY,
    *,
    model_client: ModelClient,
    prompter: Prompter | None = None,
    trace_path: str = "traces/pipeline_v03_traces.jsonl",
    num_branches: int = 4,
    event_sink: EventSink | None = None,
    session_id: str | None = None,
) -> GraphRunResult:
    """Run v0.3 and return the canonical ThoughtGraph result."""

    controller = build_v03_controller(
        model_client=model_client,
        prompter=prompter,
        trace_path=trace_path,
        num_branches=num_branches,
        event_sink=event_sink,
        session_id=session_id,
    )
    return run_controller_as_graph(controller, message)

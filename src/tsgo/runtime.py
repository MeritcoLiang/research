"""Shared runtime entrypoints for CLI demos, tests, and Web UI.

This module is the single source of truth for running a Pipeline v0.2 message.
The Web UI and `tests/demo_pipeline_v02.py` must both call
`run_pipeline_message()` so they remain equivalent.
"""

from __future__ import annotations

from .events import EventSink
from .mock_operators import build_mock_operators
from .pipeline import PipelineConfig, PipelineController
from .schema import Trace


DEFAULT_QUERY = "进入 Pipeline v0.2：跑通 Prompter、mock runner、JSON parser 和 trace 持久化。"


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

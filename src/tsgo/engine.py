"""Graph-first orchestration entrypoints.

PipelineController remains useful as a linear execution strategy, but the core
artifact returned by the project should be a ThoughtGraph. This module provides
a small graph-first wrapper without introducing a large workflow framework.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import EventSink
from .pipeline import PipelineController
from .schema import Trace
from .thought_graph import ThoughtGraph, trace_to_thought_graph


@dataclass(slots=True)
class GraphRunResult:
    """Result of one orchestration run."""

    trace: Trace
    thought_graph: ThoughtGraph

    def assert_integrity(self) -> None:
        missing = self.thought_graph.missing_edge_refs()
        if missing:
            formatted = ", ".join(f"{edge.source}->{edge.target}" for edge in missing[:10])
            raise ValueError(f"ThoughtGraph has missing edge references: {formatted}")
        if self.trace.final_state_id and self.trace.final_state_id not in self.thought_graph.states:
            raise ValueError("Trace final_state_id is not present in ThoughtGraph states.")


class ThoughtStateGraphEngine:
    """Minimal graph-first engine built on top of a controller.

    This class intentionally does not implement MCTS, DSLs, or provider routing.
    Its job is to make `ThoughtGraph` the explicit output of orchestration.
    """

    def __init__(self, controller: PipelineController) -> None:
        self.controller = controller

    def run(self, message: str) -> GraphRunResult:
        trace = self.controller.run(message)
        thought_graph = trace_to_thought_graph(trace)
        result = GraphRunResult(trace=trace, thought_graph=thought_graph)
        result.assert_integrity()
        return result


def run_controller_as_graph(controller: PipelineController, message: str) -> GraphRunResult:
    """Convenience wrapper for callers that already build a controller."""

    return ThoughtStateGraphEngine(controller).run(message)

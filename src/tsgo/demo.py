"""Command-line demo for Pipeline v0.2.

Usage:
    python -m tsgo.demo "请进入 Pipeline v0.2"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mock_operators import build_mock_operators
from .pipeline import PipelineConfig, PipelineController
from .schema import Trace


DEFAULT_QUERY = "进入 Pipeline v0.2：跑通 Prompter、mock runner、JSON parser 和 trace 持久化。"


def build_v02_controller(
    *,
    trace_path: str = "traces/pipeline_traces.jsonl",
    num_branches: int = 4,
) -> PipelineController:
    """Create a Pipeline v0.2 controller with deterministic mock operators."""

    config = PipelineConfig(
        default_num_branches=num_branches,
        max_improvement_rounds=1,
        top_k_for_aggregation=4,
        metadata={"trace_path": trace_path, "runner": "mock_v0.2"},
    )
    return PipelineController(operators=build_mock_operators(), config=config)


def run_demo(
    query: str = DEFAULT_QUERY,
    *,
    trace_path: str = "traces/pipeline_traces.jsonl",
    num_branches: int = 4,
) -> Trace:
    """Run the v0.2 mock pipeline and return the trace."""

    controller = build_v02_controller(trace_path=trace_path, num_branches=num_branches)
    return controller.run(query)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Pipeline v0.2 mock demo.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY, help="User query to run.")
    parser.add_argument(
        "--trace-path",
        default="traces/pipeline_traces.jsonl",
        help="Path to append JSONL traces.",
    )
    parser.add_argument(
        "--num-branches",
        type=int,
        default=4,
        help="Number of strategy-conditioned branches per subtask.",
    )
    parser.add_argument(
        "--pretty-trace",
        default=None,
        help="Optional path for a pretty-printed JSON trace snapshot.",
    )
    args = parser.parse_args()

    trace = run_demo(args.query, trace_path=args.trace_path, num_branches=args.num_branches)
    if args.pretty_trace:
        pretty_path = Path(args.pretty_trace)
        pretty_path.parent.mkdir(parents=True, exist_ok=True)
        pretty_path.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    final_state = next((state for state in trace.states if state.id == trace.final_state_id), None)
    print(json.dumps(
        {
            "trace_id": trace.id,
            "final_state_id": trace.final_state_id,
            "final_status": final_state.status if final_state else None,
            "state_count": len(trace.states),
            "trace_path": trace.metadata.get("trace_path"),
            "final_draft_preview": (final_state.draft or "")[:600] if final_state else None,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()

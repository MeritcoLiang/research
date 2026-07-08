#!/usr/bin/env python3
"""Test/demo adapter for Pipeline v0.2.

This file intentionally lives under tests/. It is equivalent to sending the
same message from the Web UI because both paths call tsgo.runtime.run_pipeline_message().

Usage:
    python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tsgo.runtime import DEFAULT_QUERY, run_pipeline_message  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Pipeline v0.2 test demo.")
    parser.add_argument("message", nargs="?", default=DEFAULT_QUERY, help="User message to run.")
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

    trace = run_pipeline_message(
        args.message,
        trace_path=args.trace_path,
        num_branches=args.num_branches,
    )
    if args.pretty_trace:
        pretty_path = Path(args.pretty_trace)
        pretty_path.parent.mkdir(parents=True, exist_ok=True)
        pretty_path.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    final_state = next((state for state in trace.states if state.id == trace.final_state_id), None)
    print(
        json.dumps(
            {
                "trace_id": trace.id,
                "final_state_id": trace.final_state_id,
                "final_status": final_state.status if final_state else None,
                "state_count": len(trace.states),
                "event_count": len(trace.metadata.get("events", [])),
                "trace_path": trace.metadata.get("trace_path"),
                "final_draft_preview": (final_state.draft or "")[:600] if final_state else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Demo adapter for the runnable SecondaryMarketAnalyst Stage flow.

Usage:
    python tests/demo_secondary_market_stage_flow.py "请用二级市场分析师视角分析 AAPL 的中期机会和风险。"
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

from tsgo.runtime import DEFAULT_SECONDARY_MARKET_QUERY, run_secondary_market_stage_flow  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SecondaryMarketAnalyst Stage flow.")
    parser.add_argument("message", nargs="?", default=DEFAULT_SECONDARY_MARKET_QUERY)
    parser.add_argument("--trace-path", default="traces/secondary_market_stage_flow.jsonl")
    parser.add_argument("--num-branches", type=int, default=6)
    parser.add_argument("--pretty-trace", default=None)
    args = parser.parse_args()

    trace = run_secondary_market_stage_flow(
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
                "expert_profile": trace.metadata.get("expert_profile"),
                "final_state_id": trace.final_state_id,
                "final_status": final_state.status if final_state else None,
                "subtask_count": len(trace.subtasks),
                "state_count": len(trace.states),
                "event_count": len(trace.metadata.get("events", [])),
                "trace_path": trace.metadata.get("trace_path"),
                "final_draft_preview": (final_state.draft or "")[:800] if final_state else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

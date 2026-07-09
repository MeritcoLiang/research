#!/usr/bin/env python3
"""Run Pipeline v0.3 with real DeepSeek calls.

Prerequisites:
    cp .env.example .env
    fill DEEPSEEK_API_KEY in .env

Usage:
    python tests/demo_pipeline_v03_deepseek.py "进入 Pipeline v0.3" --num-branches 1
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

from tsgo.deepseek_client import DeepSeekOpenAIChatModelClient  # noqa: E402
from tsgo.runtime import DEFAULT_V03_QUERY, run_llm_pipeline_message  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pipeline v0.3 with DeepSeek.")
    parser.add_argument("message", nargs="?", default=DEFAULT_V03_QUERY)
    parser.add_argument("--trace-path", default="traces/pipeline_v03_deepseek_traces.jsonl")
    parser.add_argument("--num-branches", type=int, default=1)
    parser.add_argument("--pretty-trace", default=None)
    args = parser.parse_args()

    client = DeepSeekOpenAIChatModelClient.from_env()
    trace = run_llm_pipeline_message(
        args.message,
        model_client=client,
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
                "deepseek_model_call_count": len(client.prompts),
                "trace_path": trace.metadata.get("trace_path"),
                "final_draft_preview": (final_state.draft or "")[:800] if final_state else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

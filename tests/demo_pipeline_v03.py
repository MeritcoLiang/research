#!/usr/bin/env python3
"""Test/demo adapter for Pipeline v0.3 LLM-backed operators.

This demo uses ScriptedModelClient so it can run without API credentials while
exercising the same LLM-backed operator path that production providers will use.
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

from tsgo.model_client import ScriptedModelClient  # noqa: E402
from tsgo.runtime import DEFAULT_V03_QUERY, run_llm_pipeline_message  # noqa: E402


def scripted_responses(num_subtasks: int, num_branches: int) -> list[str]:
    responses: list[str] = []
    for subtask_index in range(num_subtasks):
        for branch_index in range(num_branches):
            responses.append(
                json.dumps(
                    {
                        "branches": [
                            {
                                "draft": (
                                    f"Pipeline v0.3 候选：覆盖 s{subtask_index + 1} / branch {branch_index + 1}。"
                                    " 使用 LLM-backed operator、JSON 合约、trace event 和验证门禁。"
                                )
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            )
    for subtask_index in range(num_subtasks):
        for branch_index in range(num_branches):
            responses.append(
                json.dumps(
                    {
                        "summary": f"规范化 s{subtask_index + 1} branch {branch_index + 1}",
                        "claims": [
                            {
                                "text": "v0.3 应通过 LLM-backed operators 产出结构化 ThoughtState。",
                                "claim_type": "recommendation",
                                "confidence": 0.86,
                            }
                        ],
                        "assumptions": ["模型输出遵循 JSON contract。"],
                        "missing_info": [],
                        "risks": ["真实模型可能输出非 JSON，需要 parser hardening。"],
                    },
                    ensure_ascii=False,
                )
            )
    responses.append(
        json.dumps(
            {
                "scores": [
                    {
                        "correctness": 0.84,
                        "completeness": 0.82,
                        "relevance": 0.9,
                        "clarity": 0.86,
                        "groundedness": 0.78,
                        "safety": 1.0,
                        "actionability": 0.86,
                        "overall": 0.86,
                        "weaknesses": [],
                        "critical_errors": [],
                        "improvement_instructions": [],
                    }
                    for _ in range(num_subtasks * num_branches)
                ]
            },
            ensure_ascii=False,
        )
    )
    responses.append(
        json.dumps(
            {
                "draft": (
                    "# Pipeline v0.3 聚合结果\n\n"
                    "LLM-backed operators 已通过统一 ModelClient、Prompter、JSON contract、"
                    "TraceEvent 和 FinalValidator 跑通。"
                ),
                "selected_claims": [
                    {
                        "text": "v0.3 的核心是用真实模型替换 mock operator 内部实现，同时保持状态契约不变。",
                        "claim_type": "recommendation",
                        "confidence": 0.9,
                    }
                ],
                "conflicts": [],
                "resolutions": [],
                "aggregation_policy": "diversity_aware_claim_level_merge",
            },
            ensure_ascii=False,
        )
    )
    responses.append(
        json.dumps(
            {"pass": True, "blocking_issues": [], "required_edits": [], "confidence": 0.9},
            ensure_ascii=False,
        )
    )
    return responses


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Pipeline v0.3 scripted LLM demo.")
    parser.add_argument("message", nargs="?", default=DEFAULT_V03_QUERY, help="User message to run.")
    parser.add_argument("--trace-path", default="traces/pipeline_v03_traces.jsonl")
    parser.add_argument("--num-branches", type=int, default=1)
    args = parser.parse_args()

    client = ScriptedModelClient(scripted_responses(num_subtasks=4, num_branches=args.num_branches))
    trace = run_llm_pipeline_message(
        args.message,
        model_client=client,
        trace_path=args.trace_path,
        num_branches=args.num_branches,
    )
    final_state = next((state for state in trace.states if state.id == trace.final_state_id), None)
    print(
        json.dumps(
            {
                "trace_id": trace.id,
                "final_state_id": trace.final_state_id,
                "final_status": final_state.status if final_state else None,
                "state_count": len(trace.states),
                "event_count": len(trace.metadata.get("events", [])),
                "model_call_count": len(client.prompts),
                "trace_path": trace.metadata.get("trace_path"),
                "final_draft_preview": (final_state.draft or "")[:600] if final_state else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

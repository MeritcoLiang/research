from __future__ import annotations

import json
from pathlib import Path

from tsgo.model_client import ScriptedModelClient
from tsgo.runtime import run_llm_pipeline_message


def _responses(num_subtasks: int = 4, num_branches: int = 1) -> list[str]:
    responses: list[str] = []
    for subtask_index in range(num_subtasks):
        for branch_index in range(num_branches):
            responses.append(
                json.dumps(
                    {
                        "branches": [
                            {
                                "draft": (
                                    f"v0.3 candidate s{subtask_index + 1} b{branch_index + 1}: "
                                    "LLM-backed operators preserve ThoughtState contracts."
                                )
                            }
                        ]
                    }
                )
            )
    for _ in range(num_subtasks * num_branches):
        responses.append(
            json.dumps(
                {
                    "summary": "normalized candidate",
                    "claims": [
                        {
                            "text": "LLM operators should emit structured ThoughtState data.",
                            "claim_type": "recommendation",
                            "confidence": 0.88,
                        }
                    ],
                    "assumptions": ["model output is JSON"],
                    "missing_info": [],
                    "risks": [],
                }
            )
        )
    responses.append(
        json.dumps(
            {
                "scores": [
                    {
                        "correctness": 0.85,
                        "completeness": 0.82,
                        "relevance": 0.9,
                        "clarity": 0.84,
                        "groundedness": 0.8,
                        "safety": 1.0,
                        "actionability": 0.86,
                        "overall": 0.86,
                        "weaknesses": [],
                        "critical_errors": [],
                        "improvement_instructions": [],
                    }
                    for _ in range(num_subtasks * num_branches)
                ]
            }
        )
    )
    responses.append(
        json.dumps(
            {
                "draft": "# Pipeline v0.3 聚合结果\nLLM-backed operator path passed.",
                "selected_claims": [
                    {
                        "text": "v0.3 can use model output while preserving orchestration contracts.",
                        "claim_type": "recommendation",
                        "confidence": 0.9,
                    }
                ],
                "conflicts": [],
                "resolutions": [],
                "aggregation_policy": "diversity_aware_claim_level_merge",
            }
        )
    )
    responses.append(json.dumps({"pass": True, "blocking_issues": [], "required_edits": [], "confidence": 0.91}))
    return responses


def test_v03_llm_pipeline_runs_with_scripted_model(tmp_path: Path) -> None:
    client = ScriptedModelClient(_responses())
    trace_path = tmp_path / "pipeline_v03.jsonl"

    trace = run_llm_pipeline_message(
        "进入 Pipeline v0.3",
        model_client=client,
        trace_path=str(trace_path),
        num_branches=1,
    )

    final_state = next(state for state in trace.states if state.id == trace.final_state_id)
    assert final_state.status == "validated"
    assert "Pipeline v0.3" in (final_state.draft or "")
    assert trace_path.exists()
    assert len(client.prompts) == 11
    assert any(state.metadata.get("operator_mode") == "llm_v0.3" for state in trace.states)

    persisted = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    assert persisted["final_state_id"] == trace.final_state_id
    assert persisted["metadata"]["stage_logs"]["trace_logger"]["ok"] is True

from __future__ import annotations

import json
from pathlib import Path

from tsgo.runtime import run_pipeline_message


def test_v02_mock_pipeline_runs_end_to_end(tmp_path: Path) -> None:
    trace_path = tmp_path / "pipeline_traces.jsonl"
    trace = run_pipeline_message("进入 Pipeline v0.2", trace_path=str(trace_path), num_branches=2)

    assert trace.final_state_id is not None
    assert trace_path.exists()
    assert len(trace.states) > 0
    assert len(trace.metadata.get("events", [])) > 0

    final_state = next(state for state in trace.states if state.id == trace.final_state_id)
    assert final_state.status == "validated"
    assert final_state.draft is not None
    assert "Pipeline v0.2" in final_state.draft

    persisted = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
    persisted_event_types = [event["event_type"] for event in persisted["metadata"]["events"]]
    assert persisted["final_state_id"] == trace.final_state_id
    assert "pipeline_completed" in persisted_event_types
    assert "trace_persisted" in persisted_event_types
    assert "trace_logger" in persisted["metadata"]["stage_logs"]

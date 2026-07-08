from __future__ import annotations

from collections import Counter
from pathlib import Path

from tsgo.runtime import run_pipeline_message
from tsgo.web.sessions import SessionManager


def _normalized_trace_shape(trace):
    final_state = next(state for state in trace.states if state.id == trace.final_state_id)
    return {
        "stage_counts": Counter(state.stage for state in trace.states),
        "status_counts": Counter(state.status for state in trace.states),
        "final_status": final_state.status,
        "has_v02_final": "Pipeline v0.2" in (final_state.draft or ""),
        "has_events": len(trace.metadata.get("events", [])) > 0,
    }


def test_web_message_path_equivalent_to_test_demo_runtime(tmp_path: Path) -> None:
    message = "进入 Pipeline v0.2"

    cli_trace = run_pipeline_message(
        message,
        trace_path=str(tmp_path / "cli.jsonl"),
        num_branches=2,
    )

    manager = SessionManager(trace_dir=tmp_path / "web")
    session = manager.create_session()
    web_trace = manager.handle_user_message(
        session_id=session.session_id,
        message=message,
        num_branches=2,
    )

    assert _normalized_trace_shape(cli_trace) == _normalized_trace_shape(web_trace)

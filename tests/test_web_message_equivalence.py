from __future__ import annotations

from collections import Counter
from pathlib import Path

from tsgo.runtime import run_secondary_market_stage_flow
from tsgo.web.sessions import SessionManager


def _normalized_trace_shape(trace):
    final_state = next(state for state in trace.states if state.id == trace.final_state_id)
    event_types = Counter(event["event_type"] for event in trace.metadata.get("events", []))
    return {
        "stage_counts": Counter(state.stage for state in trace.states),
        "status_counts": Counter(state.status for state in trace.states),
        "final_status": final_state.status,
        "has_secondary_market_final": "二级市场分析聚合结果" in (final_state.draft or ""),
        "expert_profile": trace.metadata.get("expert_profile"),
        "has_expert_handoff": event_types["expert_handoff"] == 1,
        "has_events": len(trace.metadata.get("events", [])) > 0,
    }


def test_web_message_path_equivalent_to_secondary_market_stage_flow(tmp_path: Path) -> None:
    message = "请用二级市场分析师视角分析 AAPL 的中期机会和风险。"

    cli_trace = run_secondary_market_stage_flow(
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

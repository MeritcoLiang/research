from __future__ import annotations

from pathlib import Path

from tsgo.events import InMemoryEventSink
from tsgo.runtime import run_pipeline_message


def test_pipeline_emits_realtime_events(tmp_path: Path) -> None:
    sink = InMemoryEventSink()
    trace = run_pipeline_message(
        "进入 Pipeline v0.2",
        trace_path=str(tmp_path / "events.jsonl"),
        num_branches=2,
        event_sink=sink,
        session_id="session_test",
    )

    event_types = [event.event_type for event in sink.events]
    assert "pipeline_started" in event_types
    assert "stage_started" in event_types
    assert "state_created" in event_types
    assert "subtask_created" in event_types
    assert "edge_created" in event_types
    assert "stage_completed" in event_types
    assert "pipeline_completed" in event_types
    assert trace.metadata.get("events")

from __future__ import annotations

from pathlib import Path

from tsgo.graph import trace_to_graph
from tsgo.runtime import run_pipeline_message


def test_trace_to_graph_builds_readable_nodes_and_edges(tmp_path: Path) -> None:
    trace = run_pipeline_message(
        "进入 Pipeline v0.2",
        trace_path=str(tmp_path / "graph.jsonl"),
        num_branches=2,
    )
    graph = trace_to_graph(trace)

    labels = {node.label for node in graph.nodes}
    edge_targets = {edge.target for edge in graph.edges}

    assert graph.trace_id == trace.id
    assert len(graph.nodes) == len(trace.states) + len(trace.subtasks)
    assert len(graph.edges) > 0
    assert "root" in labels
    assert "subtask s1" in labels
    assert "aggregation" in labels
    assert "validation" in labels
    assert any(label.startswith("candidate") for label in labels)
    assert any(label.startswith("normalized") for label in labels)
    assert any(label.startswith("scored") for label in labels)
    assert all(subtask.id in edge_targets for subtask in trace.subtasks)
    assert not any("candidate_" in label or "scored_" in label for label in labels)
    assert any(node.stage == "final_validator" and node.status == "validated" for node in graph.nodes)

from __future__ import annotations

from pathlib import Path

from tsgo.graph import trace_to_graph
from tsgo.runtime import run_pipeline_message


def test_trace_to_graph_builds_nodes_and_edges(tmp_path: Path) -> None:
    trace = run_pipeline_message(
        "进入 Pipeline v0.2",
        trace_path=str(tmp_path / "graph.jsonl"),
        num_branches=2,
    )
    graph = trace_to_graph(trace)

    assert graph.trace_id == trace.id
    assert len(graph.nodes) == len(trace.states)
    assert len(graph.edges) > 0
    assert any(node.stage == "final_validator" and node.status == "validated" for node in graph.nodes)

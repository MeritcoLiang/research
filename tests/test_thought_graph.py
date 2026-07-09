from __future__ import annotations

from pathlib import Path

from tsgo.runtime import run_pipeline_graph
from tsgo.thought_graph import trace_to_thought_graph


def test_trace_converts_to_integral_thought_graph(tmp_path: Path) -> None:
    result = run_pipeline_graph(
        "进入 Pipeline v0.2",
        trace_path=str(tmp_path / "graph_engine.jsonl"),
        num_branches=2,
    )

    graph = result.thought_graph
    result.assert_integrity()

    assert graph.root_id is not None
    assert graph.final_state_id == result.trace.final_state_id
    assert len(graph.subtasks) == len(result.trace.subtasks)
    assert not graph.missing_edge_refs()
    assert any(edge.edge_type == "decomposes_to" for edge in graph.edges)
    assert any(edge.edge_type == "generates" for edge in graph.edges)
    assert any(edge.edge_type == "normalizes" for edge in graph.edges)
    assert any(edge.edge_type == "scores" for edge in graph.edges)
    assert any(edge.edge_type == "aggregates" for edge in graph.edges)
    assert any(edge.edge_type == "validates" for edge in graph.edges)

    final_lineage = graph.full_lineage(graph.final_state_id or "")
    assert graph.root_id in final_lineage
    assert graph.final_state_id in final_lineage


def test_trace_to_thought_graph_is_canonical_adapter(tmp_path: Path) -> None:
    result = run_pipeline_graph(
        "进入 Pipeline v0.2",
        trace_path=str(tmp_path / "canonical.jsonl"),
        num_branches=1,
    )
    graph = trace_to_thought_graph(result.trace)

    assert graph.to_dict()["final_state_id"] == result.trace.final_state_id
    assert not graph.missing_edge_refs()

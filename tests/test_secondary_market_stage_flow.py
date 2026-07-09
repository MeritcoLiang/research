from __future__ import annotations

from collections import Counter
from pathlib import Path

from tsgo.graph import trace_to_graph
from tsgo.runtime import run_secondary_market_graph, run_secondary_market_stage_flow


def test_secondary_market_stage_flow_runs_all_business_stages(tmp_path: Path) -> None:
    trace = run_secondary_market_stage_flow(
        "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
        trace_path=str(tmp_path / "secondary_market.jsonl"),
        num_branches=2,
    )

    final_state = next(state for state in trace.states if state.id == trace.final_state_id)
    event_types = Counter(event["event_type"] for event in trace.metadata.get("events", []))

    assert trace.metadata["expert_profile"] == "SecondaryMarketAnalyst"
    assert trace.metadata["expert_handoff"]["selected_expert"] == "SecondaryMarketAnalyst"
    assert event_types["expert_handoff"] == 1
    assert event_types["subtask_created"] == 6
    assert len(trace.subtasks) == 6
    assert len([state for state in trace.states if state.stage == "candidate_generator"]) == 12
    assert final_state.status == "validated"
    assert "Bull 情景" in (final_state.draft or "")
    assert "Base 情景" in (final_state.draft or "")
    assert "Bear 情景" in (final_state.draft or "")
    assert "不是个性化投资建议" in (final_state.draft or "")


def test_secondary_market_stage_flow_updates_graph_nodes(tmp_path: Path) -> None:
    trace = run_secondary_market_stage_flow(
        "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
        trace_path=str(tmp_path / "secondary_market_graph.jsonl"),
        num_branches=1,
    )
    graph = trace_to_graph(trace)
    labels = {node.label for node in graph.nodes}
    edge_types = {edge.edge_type for edge in graph.edges}

    assert any(label.startswith("expert") and "SecondaryMarketAnalyst" in label for label in labels)
    assert "subtask s1" in labels
    assert "aggregation" in labels
    assert "validation" in labels
    assert "handoff" in edge_types
    assert "decomposes_to" in edge_types


def test_secondary_market_graph_has_integral_lineage(tmp_path: Path) -> None:
    result = run_secondary_market_graph(
        "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
        trace_path=str(tmp_path / "secondary_market_thought_graph.jsonl"),
        num_branches=1,
    )

    graph = result.thought_graph
    result.assert_integrity()
    assert "SecondaryMarketAnalyst" in graph.expert_profiles
    assert any(edge.edge_type == "handoff" for edge in graph.edges)
    assert graph.root_id in graph.full_lineage(graph.final_state_id or "")

"""Trace-to-graph adapters for the Web UI.

The graph model keeps internal IDs for edges, but user-visible labels are
semantic and compact: root -> subtask -> candidate -> normalized -> scored ->
aggregation -> validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .events import TraceEvent
from .schema import Subtask, ThoughtState, Trace


@dataclass(slots=True)
class GraphNode:
    id: str
    label: str
    stage: str
    status: str
    score: float | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphEdge:
    id: str
    source: str
    target: str
    edge_type: str = "parent"
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphSnapshot:
    trace_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def state_to_node(state: ThoughtState) -> GraphNode:
    """Convert one ThoughtState into a frontend graph node with a semantic label."""

    score = state.score.overall if state.score else None
    return GraphNode(
        id=state.id,
        label=_state_label(state),
        stage=state.stage,
        status=state.status,
        score=score,
        summary=state.summary or (state.draft or "")[:120],
        metadata={
            "internal_id": state.id,
            "parent_ids": state.parent_ids,
            "claim_count": len(state.claims),
            "critique_count": len(state.critique),
            **state.metadata,
        },
    )


def subtask_to_node(subtask: Subtask) -> GraphNode:
    """Convert one Subtask into a visible graph node."""

    return GraphNode(
        id=subtask.id,
        label=f"subtask {subtask.id}",
        stage="problem_decomposer",
        status="subtask",
        summary=subtask.question,
        metadata={
            "internal_id": subtask.id,
            "required_outputs": subtask.required_outputs,
            "dependencies": subtask.dependencies,
            **subtask.metadata,
        },
    )


def trace_to_graph(trace: Trace) -> GraphSnapshot:
    """Build a complete graph snapshot from a trace.

    Subtasks are not ThoughtState objects, but they are important visual nodes.
    Without them, candidate parent references such as s1/s2/s3/s4 become broken
    graph edges.
    """

    nodes = [state_to_node(state) for state in trace.states]
    existing_node_ids = {node.id for node in nodes}
    edges: list[GraphEdge] = []
    seen_edges: set[str] = set()

    root_id = next((state.id for state in trace.states if state.stage == "root"), None)
    for subtask in trace.subtasks:
        if subtask.id not in existing_node_ids:
            nodes.append(subtask_to_node(subtask))
            existing_node_ids.add(subtask.id)
        if root_id:
            _append_edge(edges, seen_edges, root_id, subtask.id, "decomposes_to")

    for state in trace.states:
        for parent_id in state.parent_ids:
            _append_edge(edges, seen_edges, parent_id, state.id, "parent")
    return GraphSnapshot(trace_id=trace.id, nodes=nodes, edges=edges)


def event_to_graph_delta(event: TraceEvent) -> dict[str, Any]:
    """Convert one event into a small graph delta for WebSocket clients."""

    if event.event_type == "subtask_created":
        subtask_id = str(event.payload.get("subtask_id", event.state_id or "subtask"))
        return {
            "type": "graph_node_upsert",
            "trace_id": event.trace_id,
            "node": {
                "id": subtask_id,
                "label": f"subtask {subtask_id}",
                "stage": "problem_decomposer",
                "status": "subtask",
                "score": None,
                "summary": event.payload.get("question"),
                "metadata": event.payload.get("metadata", {}),
            },
        }

    if event.event_type == "state_created" and event.state_id:
        label = _event_state_label(event)
        return {
            "type": "graph_node_upsert",
            "trace_id": event.trace_id,
            "node": {
                "id": event.state_id,
                "label": label,
                "stage": event.stage,
                "status": event.payload.get("status"),
                "score": event.payload.get("score"),
                "summary": event.payload.get("summary") or event.payload.get("draft_preview"),
                "metadata": event.payload.get("metadata", {}),
            },
        }
    if event.event_type == "edge_created":
        source = event.payload.get("source")
        target = event.payload.get("target")
        return {
            "type": "graph_edge_upsert",
            "trace_id": event.trace_id,
            "edge": {
                "id": f"{source}->{target}",
                "source": source,
                "target": target,
                "edge_type": event.payload.get("edge_type", "parent"),
            },
        }
    if event.event_type == "score_updated" and event.state_id:
        return {
            "type": "graph_node_patch",
            "trace_id": event.trace_id,
            "node_id": event.state_id,
            "patch": {"score": event.payload.get("overall")},
        }
    return {"type": "event", "event": event.to_dict()}


def _append_edge(
    edges: list[GraphEdge],
    seen_edges: set[str],
    source: str,
    target: str,
    edge_type: str,
) -> None:
    edge_id = f"{source}->{target}"
    if edge_id in seen_edges:
        return
    seen_edges.add(edge_id)
    edges.append(GraphEdge(id=edge_id, source=source, target=target, edge_type=edge_type))


def _state_label(state: ThoughtState) -> str:
    metadata = state.metadata
    if state.stage == "root":
        return "root"
    if state.stage == "candidate_generator":
        return _candidate_label(metadata)
    if state.stage == "thought_normalizer":
        return "normalized"
    if state.stage == "verifier_scorer":
        return _scored_label(state.score.overall if state.score else None)
    if state.stage == "improver":
        return "improved"
    if state.stage == "aggregator":
        return "aggregation"
    if state.stage == "final_validator":
        return "validation"
    return state.stage


def _event_state_label(event: TraceEvent) -> str:
    metadata = event.payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    if event.stage == "root":
        return "root"
    if event.stage == "candidate_generator":
        return _candidate_label(metadata)
    if event.stage == "thought_normalizer":
        return "normalized"
    if event.stage == "verifier_scorer":
        return _scored_label(event.payload.get("score"))
    if event.stage == "improver":
        return "improved"
    if event.stage == "aggregator":
        return "aggregation"
    if event.stage == "final_validator":
        return "validation"
    return str(event.stage or "state")


def _candidate_label(metadata: dict[str, Any]) -> str:
    strategy = str(metadata.get("generation_strategy", "candidate"))
    readable_strategy = strategy.replace("_", " ")
    subtask_id = metadata.get("subtask_id")
    if subtask_id:
        return f"candidate\n{subtask_id} · {readable_strategy}"
    return f"candidate\n{readable_strategy}"


def _scored_label(score: Any) -> str:
    if isinstance(score, int | float):
        return f"scored\n{score:.2f}"
    return "scored"

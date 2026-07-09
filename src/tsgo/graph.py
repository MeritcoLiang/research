"""Trace-to-graph adapters for the Web UI.

The graph model keeps internal IDs for edges, but user-visible labels are
semantic and compact: root -> expert -> subtask -> candidate -> normalized ->
scored -> aggregation -> validation.
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


def subtask_to_node(subtask: Subtask, *, parent_id: str | None = None) -> GraphNode:
    """Convert one Subtask into a visible graph node."""

    return GraphNode(
        id=subtask.id,
        label=f"subtask {subtask.id}",
        stage="problem_decomposer",
        status="subtask",
        summary=subtask.question,
        metadata={
            "internal_id": subtask.id,
            "parent_ids": [parent_id] if parent_id else [],
            "required_outputs": subtask.required_outputs,
            "dependencies": subtask.dependencies,
            **subtask.metadata,
        },
    )


def expert_to_node(handoff: dict[str, Any]) -> GraphNode:
    expert_id = str(handoff.get("selected_expert", "expert"))
    return GraphNode(
        id=expert_id,
        label=f"expert\n{expert_id}",
        stage="expert_router",
        status="selected",
        summary=str(handoff.get("handoff_reason", "expert selected")),
        metadata={"internal_id": expert_id, "handoff": handoff},
    )


def trace_to_graph(trace: Trace) -> GraphSnapshot:
    """Build a complete graph snapshot from a trace."""

    nodes = [state_to_node(state) for state in trace.states]
    existing_node_ids = {node.id for node in nodes}
    edges: list[GraphEdge] = []
    seen_edges: set[str] = set()

    root_id = next((state.id for state in trace.states if state.stage == "root"), None)
    handoff = trace.metadata.get("expert_handoff") if isinstance(trace.metadata.get("expert_handoff"), dict) else None
    expert_id: str | None = None
    if handoff:
        expert_node = expert_to_node(handoff)
        expert_id = expert_node.id
        if expert_node.id not in existing_node_ids:
            nodes.append(expert_node)
            existing_node_ids.add(expert_node.id)
        if root_id:
            _append_edge(edges, seen_edges, root_id, expert_node.id, "handoff")

    subtask_parent = expert_id or root_id
    for subtask in trace.subtasks:
        if subtask.id not in existing_node_ids:
            nodes.append(subtask_to_node(subtask, parent_id=subtask_parent))
            existing_node_ids.add(subtask.id)
        if subtask_parent:
            _append_edge(edges, seen_edges, subtask_parent, subtask.id, "decomposes_to")

    for state in trace.states:
        for parent_id in state.parent_ids:
            _append_edge(edges, seen_edges, parent_id, state.id, "parent")
    return GraphSnapshot(trace_id=trace.id, nodes=nodes, edges=edges)


def event_to_graph_delta(event: TraceEvent) -> dict[str, Any]:
    """Convert one event into a small graph delta for WebSocket clients."""

    if event.event_type == "expert_handoff":
        expert_id = str(event.payload.get("expert_id", event.state_id or "expert"))
        metadata = _metadata_with_parent_ids(event)
        return {
            "type": "graph_node_upsert",
            "trace_id": event.trace_id,
            "node": {
                "id": expert_id,
                "label": event.payload.get("label") or f"expert\n{expert_id}",
                "stage": "expert_router",
                "status": "selected",
                "score": None,
                "summary": event.payload.get("handoff", {}).get("handoff_reason") if isinstance(event.payload.get("handoff"), dict) else None,
                "metadata": metadata,
            },
        }

    if event.event_type == "subtask_created":
        subtask_id = str(event.payload.get("subtask_id", event.state_id or "subtask"))
        metadata = _metadata_with_parent_ids(event)
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
                "metadata": metadata,
            },
        }

    if event.event_type == "state_created" and event.state_id:
        label = _event_state_label(event)
        metadata = _metadata_with_parent_ids(event)
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
                "metadata": metadata,
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


def _metadata_with_parent_ids(event: TraceEvent) -> dict[str, Any]:
    raw_metadata = event.payload.get("metadata", {})
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    metadata.setdefault("internal_id", event.state_id)
    metadata["parent_ids"] = event.parent_ids
    return metadata


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
    strategy = str(metadata.get("generation_strategy", metadata.get("branch_type", "candidate")))
    readable_strategy = strategy.replace("_", " ")
    subtask_id = metadata.get("subtask_id")
    if subtask_id:
        return f"candidate\n{subtask_id} · {readable_strategy}"
    return f"candidate\n{readable_strategy}"


def _scored_label(score: Any) -> str:
    if isinstance(score, int | float):
        return f"scored\n{score:.2f}"
    return "scored"

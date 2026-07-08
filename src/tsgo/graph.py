"""Trace-to-graph adapters for the Web UI.

The graph model is intentionally frontend-friendly: React Flow can render the
returned nodes and edges without understanding Python dataclasses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .events import TraceEvent
from .schema import ThoughtState, Trace


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
    """Convert one ThoughtState into a frontend graph node."""

    score = state.score.overall if state.score else None
    label = f"{state.stage}\n{state.id}"
    return GraphNode(
        id=state.id,
        label=label,
        stage=state.stage,
        status=state.status,
        score=score,
        summary=state.summary or (state.draft or "")[:120],
        metadata={
            "parent_ids": state.parent_ids,
            "claim_count": len(state.claims),
            "critique_count": len(state.critique),
            **state.metadata,
        },
    )


def trace_to_graph(trace: Trace) -> GraphSnapshot:
    """Build a complete graph snapshot from a trace."""

    nodes = [state_to_node(state) for state in trace.states]
    edges: list[GraphEdge] = []
    seen_edges: set[str] = set()
    for state in trace.states:
        for parent_id in state.parent_ids:
            edge_id = f"{parent_id}->{state.id}"
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(GraphEdge(id=edge_id, source=parent_id, target=state.id))
    return GraphSnapshot(trace_id=trace.id, nodes=nodes, edges=edges)


def event_to_graph_delta(event: TraceEvent) -> dict[str, Any]:
    """Convert one event into a small graph delta for WebSocket clients."""

    if event.event_type == "state_created" and event.state_id:
        return {
            "type": "graph_node_upsert",
            "trace_id": event.trace_id,
            "node": {
                "id": event.state_id,
                "label": f"{event.stage}\n{event.state_id}",
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

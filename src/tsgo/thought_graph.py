"""Core Thought-State Graph domain model.

This module is the project center of gravity. LLMs, Agents SDK, prompts, tools,
and providers are execution details. The engine's durable object is a graph of
ThoughtState nodes plus explicit edges between decomposition, generation,
normalization, scoring, improvement, aggregation, and validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4

from .schema import Subtask, ThoughtState, Trace


ThoughtEdgeType = Literal[
    "root",
    "decomposes_to",
    "generates",
    "normalizes",
    "scores",
    "improves",
    "aggregates",
    "validates",
    "feedback",
    "tool",
    "unknown",
]


@dataclass(slots=True)
class ThoughtEdge:
    """Directed edge between thought graph nodes.

    `source` and `target` may point to either a ThoughtState id or a Subtask id.
    Subtasks are first-class graph nodes because candidate states often use
    subtask ids as parents.
    """

    id: str
    source: str
    target: str
    edge_type: ThoughtEdgeType = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ThoughtGraph:
    """A replayable, queryable graph of a pipeline or graph-engine run."""

    id: str
    user_query: str
    states: dict[str, ThoughtState] = field(default_factory=dict)
    subtasks: dict[str, Subtask] = field(default_factory=dict)
    edges: list[ThoughtEdge] = field(default_factory=list)
    root_id: str | None = None
    final_state_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_state(self, state: ThoughtState) -> None:
        self.states[state.id] = state
        if state.stage == "root" and self.root_id is None:
            self.root_id = state.id

    def add_subtask(self, subtask: Subtask) -> None:
        self.subtasks[subtask.id] = subtask

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: ThoughtEdgeType = "unknown",
        **metadata: Any,
    ) -> ThoughtEdge:
        edge = ThoughtEdge(
            id=f"edge_{uuid4().hex[:12]}",
            source=source,
            target=target,
            edge_type=edge_type,
            metadata=metadata,
        )
        self.edges.append(edge)
        return edge

    def node_ids(self) -> set[str]:
        return set(self.states) | set(self.subtasks)

    def missing_edge_refs(self) -> list[ThoughtEdge]:
        ids = self.node_ids()
        return [edge for edge in self.edges if edge.source not in ids or edge.target not in ids]

    def parents_of(self, node_id: str) -> list[str]:
        return [edge.source for edge in self.edges if edge.target == node_id]

    def children_of(self, node_id: str) -> list[str]:
        return [edge.target for edge in self.edges if edge.source == node_id]

    def lineage(self, node_id: str) -> list[str]:
        """Return one parent lineage from root/subtask to the requested node.

        The graph can contain aggregation nodes with multiple parents. This
        method returns a deterministic first-parent lineage for lightweight UI
        highlighting; full lineage views should use `parents_of` recursively.
        """

        seen: set[str] = set()
        path: list[str] = []
        current = node_id
        while current and current not in seen:
            seen.add(current)
            path.append(current)
            parents = self.parents_of(current)
            if not parents:
                break
            current = parents[0]
        path.reverse()
        return path

    def full_lineage(self, node_id: str) -> set[str]:
        """Return all ancestors of a node, including the node itself."""

        visited: set[str] = set()

        def visit(current: str) -> None:
            if current in visited:
                return
            visited.add(current)
            for parent in self.parents_of(current):
                visit(parent)

        visit(node_id)
        return visited

    def states_by_stage(self, stage: str) -> list[ThoughtState]:
        return [state for state in self.states.values() if state.stage == stage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_query": self.user_query,
            "root_id": self.root_id,
            "final_state_id": self.final_state_id,
            "states": {state_id: state.to_dict() for state_id, state in self.states.items()},
            "subtasks": {subtask_id: asdict(subtask) for subtask_id, subtask in self.subtasks.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": self.metadata,
        }

    @classmethod
    def from_trace(cls, trace: Trace) -> "ThoughtGraph":
        graph = cls(
            id=f"graph_{trace.id}",
            user_query=trace.user_query,
            final_state_id=trace.final_state_id,
            metadata={"trace_id": trace.id},
        )
        for state in trace.states:
            graph.add_state(state)
        for subtask in trace.subtasks:
            graph.add_subtask(subtask)

        if graph.root_id:
            for subtask in trace.subtasks:
                graph.add_edge(graph.root_id, subtask.id, "decomposes_to")

        for state in trace.states:
            for parent_id in state.parent_ids:
                graph.add_edge(parent_id, state.id, _infer_edge_type(state))
        return graph


def trace_to_thought_graph(trace: Trace) -> ThoughtGraph:
    """Build the canonical ThoughtGraph from a Trace."""

    return ThoughtGraph.from_trace(trace)


def _infer_edge_type(state: ThoughtState) -> ThoughtEdgeType:
    if state.stage == "candidate_generator":
        return "generates"
    if state.stage == "thought_normalizer":
        return "normalizes"
    if state.stage == "verifier_scorer":
        return "scores"
    if state.stage == "improver":
        return "improves"
    if state.stage == "aggregator":
        return "aggregates"
    if state.stage == "final_validator":
        return "validates"
    return "unknown"

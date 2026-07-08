"""Deterministic Pipeline controller with optional event streaming.

Pipeline v0.2 keeps the fixed stage order from v0.1, but adds an event sink so
CLI tests and the Web UI can observe the same runtime execution path in real
time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .events import EventSink, NoopEventSink, TraceEvent
from .operators import NotImplementedOperator, Operator, OperatorResult
from .schema import ThoughtState, Trace, new_state_id


PIPELINE_STAGE_ORDER = [
    "task_intake",
    "context_builder",
    "rubric_builder",
    "problem_decomposer",
    "candidate_generator",
    "thought_normalizer",
    "verifier_scorer",
    "improver",
    "aggregator",
    "final_validator",
    "trace_logger",
]


@dataclass(slots=True)
class PipelineConfig:
    """Runtime configuration for Pipeline v0.2."""

    default_num_branches: int = 8
    max_improvement_rounds: int = 2
    top_k_for_aggregation: int = 4
    min_overall_score: float = 0.78
    min_relevance: float = 0.85
    min_correctness: float = 0.75
    min_clarity: float = 0.75
    min_groundedness: float = 0.60
    min_safety: float = 0.95
    enable_decomposition: bool = True
    enable_normalization: bool = True
    enable_claim_level_merge: bool = True
    enable_final_validation: bool = True
    enable_trace_logging: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineController:
    """Pipeline-first orchestrator.

    v0.2 is still intentionally conservative:
    - fixed stage order
    - structured state passed between stages
    - traceable parent/child state lineage
    - optional event streaming for observability
    - no arbitrary graph scheduling yet
    """

    def __init__(
        self,
        operators: dict[str, Operator] | None = None,
        config: PipelineConfig | None = None,
        event_sink: EventSink | None = None,
        session_id: str | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.event_sink = event_sink or NoopEventSink()
        self.session_id = session_id
        self.operators: dict[str, Operator] = {
            stage: NotImplementedOperator(stage) for stage in PIPELINE_STAGE_ORDER
        }
        if operators:
            self.operators.update(operators)

    def run(self, user_query: str) -> Trace:
        """Run the fixed v0.2 pipeline and return a replayable trace."""

        trace = Trace(id=new_state_id("trace"), user_query=user_query)
        self._emit(trace, "pipeline_started", payload={"user_query": user_query})

        root = ThoughtState(
            id=new_state_id("root"),
            parent_ids=[],
            stage="root",
            user_query=user_query,
            draft=user_query,
            status="draft",
        )
        trace.add_state(root)
        self._emit_state_event(trace, "state_created", root)

        active_states = [root]
        for stage_name in PIPELINE_STAGE_ORDER:
            operator = self.operators[stage_name]
            self._emit(
                trace,
                "stage_started",
                stage=stage_name,
                payload={"active_state_ids": [state.id for state in active_states]},
            )
            try:
                result = operator.run(
                    user_query=user_query,
                    states=active_states,
                    trace=trace,
                    context=trace.context,
                    rubric=trace.rubric,
                    config=self.config,
                )
            except Exception as exc:
                self._emit(
                    trace,
                    "pipeline_error",
                    stage=stage_name,
                    payload={"error": str(exc), "operator": operator.__class__.__name__},
                )
                raise

            self._record_result(trace, stage_name, result)
            if result.new_states:
                active_states = result.new_states

        if active_states:
            trace.final_state_id = active_states[-1].id
        self._emit(
            trace,
            "pipeline_completed",
            payload={"final_state_id": trace.final_state_id, "state_count": len(trace.states)},
        )
        return trace

    def _record_result(self, trace: Trace, stage_name: str, result: OperatorResult) -> None:
        for state in result.new_states:
            trace.add_state(state)
            self._emit_state_event(trace, "state_created", state)
            for parent_id in state.parent_ids:
                self._emit(
                    trace,
                    "edge_created",
                    stage=stage_name,
                    state_id=state.id,
                    parent_ids=[parent_id],
                    payload={"source": parent_id, "target": state.id, "edge_type": "parent"},
                )
            if state.score is not None:
                self._emit(
                    trace,
                    "score_updated",
                    stage=stage_name,
                    state_id=state.id,
                    parent_ids=state.parent_ids,
                    payload={"overall": state.score.overall, "score": state.score.__dict__},
                )

        trace.metadata.setdefault("stage_logs", {})[stage_name] = {
            "ok": result.ok,
            "logs": result.logs,
            "errors": result.errors,
            "metadata": result.metadata,
        }
        self._emit(
            trace,
            "stage_completed",
            stage=stage_name,
            payload={
                "ok": result.ok,
                "new_state_ids": [state.id for state in result.new_states],
                "logs": result.logs,
                "errors": result.errors,
                "metadata": result.metadata,
            },
        )

    def _emit_state_event(self, trace: Trace, event_type: str, state: ThoughtState) -> None:
        self._emit(
            trace,
            event_type,
            stage=state.stage,
            state_id=state.id,
            parent_ids=state.parent_ids,
            payload={
                "status": state.status,
                "summary": state.summary,
                "draft_preview": (state.draft or "")[:240],
                "score": state.score.overall if state.score else None,
                "claim_count": len(state.claims),
                "metadata": state.metadata,
            },
        )

    def _emit(
        self,
        trace: Trace,
        event_type: str,
        *,
        stage: str | None = None,
        state_id: str | None = None,
        parent_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = TraceEvent.create(
            trace_id=trace.id,
            session_id=self.session_id,
            event_type=event_type,
            stage=stage,
            state_id=state_id,
            parent_ids=parent_ids or [],
            payload=payload or {},
        )
        trace.metadata.setdefault("events", []).append(event.to_dict())
        self.event_sink.emit(event)

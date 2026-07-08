"""Deterministic Pipeline v0.1 controller skeleton.

This module intentionally implements a fixed stage order first. The future
Thought-State Graph Orchestration Engine can replace this controller with a DAG
or arbitrary graph scheduler without changing the core ThoughtState schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    """Runtime configuration for Pipeline v0.1."""

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

    v0.1 is intentionally conservative:
    - fixed stage order
    - structured state passed between stages
    - traceable parent/child state lineage
    - no arbitrary graph scheduling yet
    """

    def __init__(
        self,
        operators: dict[str, Operator] | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.operators: dict[str, Operator] = {
            stage: NotImplementedOperator(stage) for stage in PIPELINE_STAGE_ORDER
        }
        if operators:
            self.operators.update(operators)

    def run(self, user_query: str) -> Trace:
        """Run the fixed v0.1 pipeline and return a replayable trace.

        Concrete operators are expected to progressively enrich the trace with
        task info, context packets, rubrics, subtasks, states, and validation
        metadata.
        """

        trace = Trace(id=new_state_id("trace"), user_query=user_query)
        root = ThoughtState(
            id=new_state_id("root"),
            parent_ids=[],
            stage="root",
            user_query=user_query,
            draft=user_query,
            status="draft",
        )
        trace.add_state(root)

        active_states = [root]
        for stage_name in PIPELINE_STAGE_ORDER:
            operator = self.operators[stage_name]
            result = operator.run(
                user_query=user_query,
                states=active_states,
                trace=trace,
                context=trace.context,
                rubric=trace.rubric,
                config=self.config,
            )
            self._record_result(trace, stage_name, result)
            if result.new_states:
                active_states = result.new_states

        if active_states:
            trace.final_state_id = active_states[-1].id
        return trace

    def _record_result(self, trace: Trace, stage_name: str, result: OperatorResult) -> None:
        for state in result.new_states:
            trace.add_state(state)
        trace.metadata.setdefault("stage_logs", {})[stage_name] = {
            "ok": result.ok,
            "logs": result.logs,
            "errors": result.errors,
            "metadata": result.metadata,
        }

"""LLM-backed operators for Pipeline v0.3.

These operators use the same ThoughtState / OperatorResult / Trace contracts as
v0.2, but replace deterministic mock transformations with model calls and
schema-driven JSON parsing.
"""

from __future__ import annotations

from typing import Any

from .json_contracts import (
    parse_aggregate_packet,
    parse_generate_packet,
    parse_improve_packet,
    parse_normalize_packet,
    parse_score_packets,
    parse_validation_packet,
)
from .mock_operators import (
    DEFAULT_GENERATION_STRATEGIES,
    ContextBuilderOperator,
    ProblemDecomposerOperator,
    RubricBuilderOperator,
    TaskIntakeOperator,
    TraceLoggerOperator,
)
from .model_client import ModelClient
from .operators import Operator, OperatorResult
from .parsing import JsonParseError
from .prompter import DefaultPipelinePrompter, Prompter
from .schema import ContextPacket, Rubric, Score, Subtask, ThoughtState, Trace, new_state_id


class LLMCandidateGeneratorOperator(Operator):
    """Generate candidate states by calling a model with generate prompts."""

    name = "candidate_generator"

    def __init__(self, model_client: ModelClient, prompter: Prompter | None = None) -> None:
        self.model_client = model_client
        self.prompter = prompter or DefaultPipelinePrompter()

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        config = kwargs.get("config")
        num_branches = int(getattr(config, "default_num_branches", 4))
        strategies = DEFAULT_GENERATION_STRATEGIES[: max(1, min(num_branches, len(DEFAULT_GENERATION_STRATEGIES)))]
        subtasks = trace.subtasks or [Subtask(id="s1", question=user_query, task_type="unknown")]
        generated: list[ThoughtState] = []
        errors: list[str] = []

        for item in subtasks:
            for branch_index, strategy in enumerate(strategies):
                prompt = self.prompter.generate_prompt(
                    num_branches=1,
                    user_query=user_query,
                    context=trace.context,
                    rubric=trace.rubric,
                    subtask=item,
                    strategy=strategy,
                )
                raw = self.model_client.generate(prompt)
                try:
                    drafts = parse_generate_packet(raw)
                except JsonParseError as exc:
                    errors.append(f"generate parse failed for {item.id}/{strategy}: {exc}")
                    continue
                for local_index, draft in enumerate(drafts):
                    generated.append(
                        ThoughtState(
                            id=new_state_id("candidate"),
                            parent_ids=[item.id],
                            stage="candidate_generator",
                            user_query=user_query,
                            task_type=item.task_type,
                            draft=draft,
                            status="draft",
                            metadata={
                                "generation_strategy": strategy,
                                "branch_index": branch_index + local_index,
                                "subtask_id": item.id,
                                "prompt_preview": prompt[:240],
                                "raw_model_preview": raw[:240],
                                "operator_mode": "llm_v0.3",
                            },
                        )
                    )
        return OperatorResult(new_states=generated, errors=errors, logs=[f"LLM 生成候选数量：{len(generated)}"])


class LLMThoughtNormalizerOperator(Operator):
    """Normalize drafts into claims and risks through the model."""

    name = "thought_normalizer"

    def __init__(self, model_client: ModelClient) -> None:
        self.model_client = model_client

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        normalized: list[ThoughtState] = []
        errors: list[str] = []
        for state in states:
            prompt = _normalization_prompt(state, trace.context, trace.rubric)
            raw = self.model_client.generate(prompt)
            try:
                packet = parse_normalize_packet(raw)
            except JsonParseError as exc:
                errors.append(f"normalize parse failed for {state.id}: {exc}")
                continue
            normalized.append(
                _clone_state(
                    state,
                    prefix="normalized",
                    stage="thought_normalizer",
                    status="normalized",
                    summary=packet["summary"],
                    claims=packet["claims"],
                    assumptions=packet["assumptions"],
                    missing_info=packet["missing_info"],
                    failure_modes=packet["failure_modes"],
                    metadata={**state.metadata, "operator_mode": "llm_v0.3"},
                )
            )
        return OperatorResult(new_states=normalized, errors=errors, logs=[f"LLM 规范化状态数量：{len(normalized)}"])


class LLMVerifierScorerOperator(Operator):
    """Score normalized states through the model and attach critique."""

    name = "verifier_scorer"

    def __init__(self, model_client: ModelClient, prompter: Prompter | None = None) -> None:
        self.model_client = model_client
        self.prompter = prompter or DefaultPipelinePrompter()

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        active_rubric = trace.rubric or rubric
        weights = active_rubric.weight_map() if active_rubric else {}
        prompt = self.prompter.score_prompt(
            state_dicts=[state.to_dict() for state in states],
            context=trace.context,
            rubric=trace.rubric,
        )
        raw = self.model_client.generate(prompt)
        try:
            packets = parse_score_packets(raw, weights=weights)
        except JsonParseError as exc:
            return OperatorResult(errors=[f"score parse failed: {exc}"])

        by_id = {packet["state_id"]: packet for packet in packets if packet.get("state_id")}
        scored: list[ThoughtState] = []
        for index, state in enumerate(states):
            packet = by_id.get(state.id)
            if packet is None and index < len(packets):
                packet = packets[index]
            if packet is None:
                score = Score(notes=["missing score packet"])
                critique = ["模型没有返回该 state 的评分。"]
            else:
                score = packet["score"]
                critique = packet["weaknesses"] + packet["critical_errors"] + packet["improvement_instructions"]
            scored.append(
                _clone_state(
                    state,
                    prefix="scored",
                    stage="verifier_scorer",
                    status="scored",
                    score=score,
                    critique=critique,
                    metadata={**state.metadata, "operator_mode": "llm_v0.3"},
                )
            )
        return OperatorResult(new_states=scored, logs=[f"LLM 评分状态数量：{len(scored)}"])


class LLMImproverOperator(Operator):
    """Repair promising but under-threshold states through the model."""

    name = "improver"

    def __init__(self, model_client: ModelClient, prompter: Prompter | None = None) -> None:
        self.model_client = model_client
        self.prompter = prompter or DefaultPipelinePrompter()

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        config = kwargs.get("config")
        min_score = float(getattr(config, "min_overall_score", 0.78))
        improved: list[ThoughtState] = []
        errors: list[str] = []
        for state in states:
            if not state.score or state.score.overall >= min_score:
                continue
            prompt = self.prompter.improve_prompt(
                state=state.to_dict(),
                critique=state.critique,
                rubric=trace.rubric,
                context=trace.context,
            )
            raw = self.model_client.generate(prompt)
            try:
                packet = parse_improve_packet(raw)
            except JsonParseError as exc:
                errors.append(f"improve parse failed for {state.id}: {exc}")
                continue
            improved.append(
                _clone_state(
                    state,
                    prefix="improved",
                    stage="improver",
                    status="improved",
                    draft=packet["draft"],
                    critique=packet["change_summary"],
                    metadata={**state.metadata, "operator_mode": "llm_v0.3", "improvement_round": 1},
                )
            )
        return OperatorResult(new_states=improved, errors=errors, logs=[f"LLM 改进状态数量：{len(improved)}"])


class LLMAggregatorOperator(Operator):
    """Aggregate a diversity-aware top candidate pool through the model."""

    name = "aggregator"

    def __init__(self, model_client: ModelClient, prompter: Prompter | None = None) -> None:
        self.model_client = model_client
        self.prompter = prompter or DefaultPipelinePrompter()

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        config = kwargs.get("config")
        top_k = int(getattr(config, "top_k_for_aggregation", 4))
        pool = [state for state in trace.states if state.status in {"scored", "improved"} and state.score]
        top_states = _select_diverse_top_states(pool, top_k=top_k)
        if not top_states:
            return OperatorResult(errors=["没有可聚合的 scored/improved states。"])

        prompt = self.prompter.aggregation_prompt(
            state_dicts=[state.to_dict() for state in top_states],
            context=trace.context,
            rubric=trace.rubric,
            aggregation_policy="diversity_aware_claim_level_merge",
        )
        raw = self.model_client.generate(prompt)
        try:
            packet = parse_aggregate_packet(raw)
        except JsonParseError as exc:
            return OperatorResult(errors=[f"aggregate parse failed: {exc}"])

        aggregated = ThoughtState(
            id=new_state_id("aggregated"),
            parent_ids=[state.id for state in top_states],
            stage="aggregator",
            user_query=user_query,
            task_type=top_states[0].task_type,
            draft=packet["draft"],
            summary="Pipeline v0.3 LLM-backed aggregation result.",
            claims=packet["selected_claims"],
            score=top_states[0].score,
            status="aggregated",
            metadata={
                "aggregation_policy": packet["aggregation_policy"],
                "selected_state_ids": [state.id for state in top_states],
                "selected_subtask_ids": [state.metadata.get("subtask_id") for state in top_states],
                "conflicts": packet["conflicts"],
                "resolutions": packet["resolutions"],
                "operator_mode": "llm_v0.3",
            },
        )
        return OperatorResult(new_states=[aggregated], logs=[f"LLM 聚合 top_k={len(top_states)}。"])


class LLMFinalValidatorOperator(Operator):
    """Validate the final aggregated answer through the model."""

    name = "final_validator"

    def __init__(self, model_client: ModelClient, prompter: Prompter | None = None) -> None:
        self.model_client = model_client
        self.prompter = prompter or DefaultPipelinePrompter()

    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None = None,
        rubric: Rubric | None = None,
        subtask: Subtask | None = None,
        **kwargs: Any,
    ) -> OperatorResult:
        if not states:
            return OperatorResult(errors=["没有可验证的状态。"])
        state = states[-1]
        prompt = self.prompter.validation_prompt(
            state=state.to_dict(),
            user_query=user_query,
            context=trace.context,
            rubric=trace.rubric,
        )
        raw = self.model_client.generate(prompt)
        try:
            packet = parse_validation_packet(raw)
        except JsonParseError as exc:
            return OperatorResult(errors=[f"validation parse failed: {exc}"])

        status = "validated" if packet["pass"] else "rejected"
        validated = _clone_state(
            state,
            prefix="validated" if packet["pass"] else "rejected",
            stage="final_validator",
            status=status,
            metadata={
                **state.metadata,
                "validation": packet,
                "operator_mode": "llm_v0.3",
            },
        )
        errors = [] if packet["pass"] else packet["blocking_issues"]
        return OperatorResult(new_states=[validated], errors=errors, logs=[f"LLM 最终验证 pass={packet['pass']}"])


def build_llm_operators(model_client: ModelClient, prompter: Prompter | None = None) -> dict[str, Operator]:
    """Return the Pipeline v0.3 LLM-backed operator set."""

    return {
        "task_intake": TaskIntakeOperator(),
        "context_builder": ContextBuilderOperator(),
        "rubric_builder": RubricBuilderOperator(),
        "problem_decomposer": ProblemDecomposerOperator(),
        "candidate_generator": LLMCandidateGeneratorOperator(model_client, prompter),
        "thought_normalizer": LLMThoughtNormalizerOperator(model_client),
        "verifier_scorer": LLMVerifierScorerOperator(model_client, prompter),
        "improver": LLMImproverOperator(model_client, prompter),
        "aggregator": LLMAggregatorOperator(model_client, prompter),
        "final_validator": LLMFinalValidatorOperator(model_client, prompter),
        "trace_logger": TraceLoggerOperator(),
    }


def _normalization_prompt(state: ThoughtState, context: ContextPacket | None, rubric: Rubric | None) -> str:
    return (
        "你是 Pipeline v0.3 的 Thought Normalizer。\n"
        "请把候选 draft 规范化成 JSON，不要添加 draft 中没有的主张。\n"
        "返回 JSON schema：{\"summary\": \"...\", \"claims\": [{\"text\": \"...\", "
        "\"claim_type\": \"recommendation\", \"confidence\": 0.0}], \"assumptions\": [], "
        "\"missing_info\": [], \"risks\": []}\n"
        f"Context: {context}\n"
        f"Rubric: {rubric}\n"
        f"State: {state.to_dict()}"
    )


def _clone_state(
    state: ThoughtState,
    *,
    prefix: str,
    stage: str,
    status: str,
    **updates: Any,
) -> ThoughtState:
    data: dict[str, Any] = {
        "id": new_state_id(prefix),
        "parent_ids": [state.id],
        "stage": stage,
        "user_query": state.user_query,
        "task_type": state.task_type,
        "draft": state.draft,
        "summary": state.summary,
        "claims": list(state.claims),
        "assumptions": list(state.assumptions),
        "missing_info": list(state.missing_info),
        "evidence": list(state.evidence),
        "tool_outputs": list(state.tool_outputs),
        "critique": list(state.critique),
        "score": state.score,
        "uncertainty": list(state.uncertainty),
        "failure_modes": list(state.failure_modes),
        "status": status,
        "metadata": dict(state.metadata),
    }
    data.update(updates)
    return ThoughtState(**data)


def _select_diverse_top_states(states: list[ThoughtState], *, top_k: int) -> list[ThoughtState]:
    """Select at least one high-scoring state per subtask before global fill."""

    sorted_states = sorted(states, key=lambda state: state.score.overall if state.score else 0.0, reverse=True)
    by_subtask: dict[str, list[ThoughtState]] = {}
    for state in sorted_states:
        subtask_id = str(state.metadata.get("subtask_id", "unknown"))
        by_subtask.setdefault(subtask_id, []).append(state)

    selected: list[ThoughtState] = []
    for group in by_subtask.values():
        if group and len(selected) < top_k:
            selected.append(group[0])

    selected_ids = {state.id for state in selected}
    for state in sorted_states:
        if len(selected) >= top_k:
            break
        if state.id not in selected_ids:
            selected.append(state)
            selected_ids.add(state.id)
    return selected

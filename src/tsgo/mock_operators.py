"""Concrete deterministic operators for Pipeline v0.2.

These operators make the pipeline runnable without an LLM. They are intentionally
simple and transparent: v0.2 proves the orchestration contracts, state lineage,
trace persistence, and end-to-end data flow before v0.3 swaps in LLM-backed
operators.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .model_client import EchoModelClient, ModelClient
from .operators import Operator, OperatorResult
from .prompter import DefaultPipelinePrompter, Prompter
from .schema import (
    Claim,
    ContextPacket,
    Rubric,
    RubricItem,
    Score,
    Subtask,
    TaskInfo,
    TaskType,
    ThoughtState,
    Trace,
    new_state_id,
)
from .trace_store import JsonlTraceSink


DEFAULT_GENERATION_STRATEGIES = [
    "direct_expert",
    "system_architect",
    "implementation_first",
    "evaluation_first",
    "skeptical_reviewer",
    "risk_reviewer",
    "minimal_mvp",
    "traceability_first",
]


class TaskIntakeOperator(Operator):
    """Classify the user request and populate trace.task_info."""

    name = "task_intake"

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
        task_type = _classify_task_type(user_query)
        difficulty = "high" if len(user_query) > 80 or task_type == "system_design" else "medium"
        trace.task_info = TaskInfo(
            user_query=user_query,
            task_type=task_type,
            difficulty=difficulty,
            requires_tools=_contains_any(user_query, ["代码", "运行", "测试", "工具", "tool", "test"]),
            requires_citations=_contains_any(user_query, ["引用", "来源", "citation", "source"]),
            requires_computation=_contains_any(user_query, ["计算", "统计", "数据", "compute"]),
            requires_user_context=False,
            answer_format="technical_plan" if task_type in {"system_design", "architecture"} else "structured_text",
            metadata={"operator": self.name},
        )
        return OperatorResult(logs=[f"任务类型：{task_type}，难度：{difficulty}"])


class ContextBuilderOperator(Operator):
    """Build an explicit ContextPacket from the user query."""

    name = "context_builder"

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
        hard_constraints = _extract_hard_constraints(user_query)
        soft_preferences = _extract_soft_preferences(user_query)
        trace.context = ContextPacket(
            user_intent=f"围绕用户请求构建可执行回答：{user_query}",
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            available_context=[
                "Pipeline v0.2 使用 deterministic mock operators 跑通完整编排流程。",
                "当前重点是 prompter 契约、JSON parser、trace 持久化和端到端 demo。",
            ],
            missing_context=[],
            retrieved_evidence=[],
            tool_plan=[],
            metadata={"operator": self.name},
        )
        return OperatorResult(logs=[f"硬约束数量：{len(hard_constraints)}"])


class RubricBuilderOperator(Operator):
    """Create a task-specific rubric before candidate generation."""

    name = "rubric_builder"

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
        ctx = trace.context or ContextPacket(user_intent=user_query)
        trace.rubric = Rubric(
            items=[
                RubricItem("correctness", 0.25, "事实与逻辑正确性", 0.75),
                RubricItem("completeness", 0.18, "覆盖用户需求的完整度", 0.70),
                RubricItem("relevance", 0.18, "与用户当前请求的相关性", 0.80),
                RubricItem("clarity", 0.12, "结构清晰度", 0.70),
                RubricItem("groundedness", 0.10, "是否基于上下文、证据或明确约束", 0.60),
                RubricItem("safety", 0.07, "安全与合规风险", 0.95),
                RubricItem("actionability", 0.10, "工程可执行性", 0.70),
            ],
            hard_constraints=ctx.hard_constraints,
            soft_preferences=ctx.soft_preferences,
        )
        return OperatorResult(logs=["已构建默认工程设计 rubric。"])


class ProblemDecomposerOperator(Operator):
    """Split the request into traceable subtasks."""

    name = "problem_decomposer"

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
        task_type = trace.task_info.task_type if trace.task_info else "unknown"
        if task_type in {"system_design", "architecture"} or len(user_query) > 40:
            trace.subtasks = [
                Subtask(
                    id="s1",
                    question="明确 v0.2 的工程目标、边界和交付物。",
                    task_type=task_type,
                    required_outputs=["目标", "非目标", "交付物"],
                ),
                Subtask(
                    id="s2",
                    question="设计可运行的 mock pipeline operators。",
                    task_type=task_type,
                    required_outputs=["operator 列表", "输入输出", "状态谱系"],
                    dependencies=["s1"],
                ),
                Subtask(
                    id="s3",
                    question="设计 trace 持久化与 demo CLI。",
                    task_type=task_type,
                    required_outputs=["trace sink", "demo command", "输出格式"],
                    dependencies=["s1"],
                ),
                Subtask(
                    id="s4",
                    question="定义进入 v0.3 前的验收标准。",
                    task_type=task_type,
                    required_outputs=["验收标准", "下一步"],
                    dependencies=["s2", "s3"],
                ),
            ]
        else:
            trace.subtasks = [
                Subtask(id="s1", question=user_query, task_type=task_type, required_outputs=["answer"])
            ]
        return OperatorResult(logs=[f"已拆解为 {len(trace.subtasks)} 个 subtasks。"])


class CandidateGeneratorOperator(Operator):
    """Generate deterministic strategy-conditioned candidates."""

    name = "candidate_generator"

    def __init__(
        self,
        prompter: Prompter | None = None,
        model_client: ModelClient | None = None,
    ) -> None:
        self.prompter = prompter or DefaultPipelinePrompter()
        self.model_client = model_client or EchoModelClient()

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
                model_preview = self.model_client.generate(prompt)
                draft = _candidate_draft(user_query, item, strategy)
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
                            "branch_index": branch_index,
                            "subtask_id": item.id,
                            "prompt_preview": prompt[:240],
                            "model_preview": model_preview[:240],
                        },
                    )
                )
        return OperatorResult(new_states=generated, logs=[f"生成候选数量：{len(generated)}"])


class ThoughtNormalizerOperator(Operator):
    """Normalize raw drafts into claims, assumptions, and risks."""

    name = "thought_normalizer"

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
        for state in states:
            sentences = _split_sentences(state.draft or "")
            claims = [
                Claim(text=sentence, claim_type=_infer_claim_type(sentence), confidence=0.72)
                for sentence in sentences[:8]
            ]
            normalized.append(
                _clone_state(
                    state,
                    prefix="normalized",
                    stage="thought_normalizer",
                    status="normalized",
                    summary=_summarize(state.draft or ""),
                    claims=claims,
                    assumptions=["用户希望获得工程可落地的阶段性实现。"],
                    failure_modes=_detect_risks(state.draft or ""),
                )
            )
        return OperatorResult(new_states=normalized, logs=[f"规范化状态数量：{len(normalized)}"])


class VerifierScorerOperator(Operator):
    """Score normalized states with deterministic heuristics."""

    name = "verifier_scorer"

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
        scored: list[ThoughtState] = []
        active_rubric = trace.rubric or rubric
        weights = active_rubric.weight_map() if active_rubric else {}
        for state in states:
            score = _score_state(state, user_query, weights)
            critique = _critique_from_score(score)
            scored.append(
                _clone_state(
                    state,
                    prefix="scored",
                    stage="verifier_scorer",
                    status="scored",
                    score=score,
                    critique=critique,
                )
            )
        return OperatorResult(new_states=scored, logs=[f"评分状态数量：{len(scored)}"])


class ImproverOperator(Operator):
    """Repair promising low-scoring states."""

    name = "improver"

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
        max_rounds = int(getattr(config, "max_improvement_rounds", 1))
        improved: list[ThoughtState] = []
        candidates = sorted(
            [state for state in states if state.score is not None],
            key=lambda item: item.score.overall if item.score else 0.0,
            reverse=True,
        )[:4]

        if max_rounds <= 0:
            return OperatorResult(logs=["max_improvement_rounds=0，跳过改进。"])

        for state in candidates:
            if state.score and state.score.overall >= min_score:
                continue
            repaired_draft = (
                f"{state.draft}\n\n"
                "改进补充：补齐 v0.2 验收标准，包括可运行 demo、trace 持久化、"
                "Prompter 契约、JSON parser，以及进入 v0.3 前的明确边界。"
            )
            score = state.score or Score()
            boosted = Score(
                correctness=min(1.0, score.correctness + 0.05),
                completeness=min(1.0, score.completeness + 0.12),
                relevance=score.relevance,
                clarity=min(1.0, score.clarity + 0.05),
                groundedness=min(1.0, score.groundedness + 0.05),
                safety=score.safety,
                actionability=min(1.0, score.actionability + 0.10),
                novelty=score.novelty,
                notes=["mock improver boosted completeness/actionability"],
            )
            weights = trace.rubric.weight_map() if trace.rubric else {}
            boosted.recompute_overall(weights)
            improved.append(
                _clone_state(
                    state,
                    prefix="improved",
                    stage="improver",
                    status="improved",
                    draft=repaired_draft,
                    score=boosted,
                    critique=["已根据 verifier feedback 增加验收标准与工程边界。"],
                    metadata={**state.metadata, "improvement_round": 1},
                )
            )
        return OperatorResult(new_states=improved, logs=[f"改进状态数量：{len(improved)}"])


class AggregatorOperator(Operator):
    """Aggregate top scored/improved states into one final candidate."""

    name = "aggregator"

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
        pool = [
            state
            for state in trace.states
            if state.status in {"scored", "improved"} and state.score is not None
        ]
        top_states = sorted(
            pool,
            key=lambda item: item.score.overall if item.score else 0.0,
            reverse=True,
        )[:top_k]
        if not top_states:
            return OperatorResult(errors=["没有可聚合的 scored/improved states。"])

        final_claims = _deduplicate_claims([claim for state in top_states for claim in state.claims])
        draft = _aggregate_draft(user_query, top_states, final_claims)
        aggregated = ThoughtState(
            id=new_state_id("aggregated"),
            parent_ids=[state.id for state in top_states],
            stage="aggregator",
            user_query=user_query,
            task_type=top_states[0].task_type,
            draft=draft,
            summary="Pipeline v0.2 mock runner 端到端聚合结果。",
            claims=final_claims,
            assumptions=["v0.2 的目标是先跑通工程闭环，而不是接入真实 LLM。"],
            score=top_states[0].score,
            status="aggregated",
            metadata={
                "aggregation_policy": "claim_level_weighted_merge",
                "selected_state_ids": [state.id for state in top_states],
                "conflicts": [],
                "resolutions": [],
            },
        )
        return OperatorResult(new_states=[aggregated], logs=[f"聚合 top_k={len(top_states)}。"])


class FinalValidatorOperator(Operator):
    """Final release gate for the aggregated answer."""

    name = "final_validator"

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
        blocking: list[str] = []
        if not state.draft:
            blocking.append("最终 draft 为空。")
        if "trace" not in (state.draft or "").lower():
            blocking.append("最终答案没有体现 trace 能力。")
        pass_validation = not blocking
        validated = _clone_state(
            state,
            prefix="validated" if pass_validation else "rejected",
            stage="final_validator",
            status="validated" if pass_validation else "rejected",
            metadata={
                **state.metadata,
                "validation": {
                    "pass": pass_validation,
                    "blocking_issues": blocking,
                    "required_edits": [],
                    "confidence": 0.86 if pass_validation else 0.35,
                },
            },
        )
        errors = [] if pass_validation else blocking
        return OperatorResult(new_states=[validated], errors=errors, logs=[f"最终验证 pass={pass_validation}"])


class TraceLoggerOperator(Operator):
    """Persist the trace to local JSONL."""

    name = "trace_logger"

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
        metadata = getattr(config, "metadata", {}) if config else {}
        trace_path = Path(str(metadata.get("trace_path", "traces/pipeline_traces.jsonl")))
        sink = JsonlTraceSink(trace_path)
        written = sink.write(trace)
        trace.metadata["trace_path"] = str(written)
        return OperatorResult(logs=[f"trace 已写入：{written}"], metadata={"trace_path": str(written)})


def build_mock_operators(
    prompter: Prompter | None = None,
    model_client: ModelClient | None = None,
) -> dict[str, Operator]:
    """Return the complete v0.2 deterministic operator set."""

    return {
        "task_intake": TaskIntakeOperator(),
        "context_builder": ContextBuilderOperator(),
        "rubric_builder": RubricBuilderOperator(),
        "problem_decomposer": ProblemDecomposerOperator(),
        "candidate_generator": CandidateGeneratorOperator(prompter=prompter, model_client=model_client),
        "thought_normalizer": ThoughtNormalizerOperator(),
        "verifier_scorer": VerifierScorerOperator(),
        "improver": ImproverOperator(),
        "aggregator": AggregatorOperator(),
        "final_validator": FinalValidatorOperator(),
        "trace_logger": TraceLoggerOperator(),
    }


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


def _classify_task_type(query: str) -> TaskType:
    lowered = query.lower()
    if _contains_any(lowered, ["pipeline", "orchestration", "架构", "工程", "engine", "v0.2"]):
        return "system_design"
    if _contains_any(lowered, ["代码", "bug", "test", "function", "class"]):
        return "coding"
    if _contains_any(lowered, ["研究", "资料", "论文", "source", "citation"]):
        return "research"
    if _contains_any(lowered, ["计划", "路线图", "roadmap"]):
        return "planning"
    return "mixed"


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _extract_hard_constraints(query: str) -> list[str]:
    markers = ["必须", "需要", "不要", "先", "改用", "进入", "must", "need", "do not"]
    return [query] if _contains_any(query, markers) else []


def _extract_soft_preferences(query: str) -> list[str]:
    preferences: list[str] = []
    if _contains_any(query, ["中文", "Chinese"]):
        preferences.append("文档优先使用中文，代码标识符保持英文。")
    if _contains_any(query, ["前沿", "实验室", "frontier"]):
        preferences.append("方案应体现前沿实验室式工程方法。")
    return preferences


def _candidate_draft(user_query: str, subtask: Subtask, strategy: str) -> str:
    return (
        f"策略：{strategy}\n"
        f"子任务：{subtask.question}\n"
        f"针对用户请求：{user_query}\n"
        "建议：在 v0.2 中先跑通 deterministic mock pipeline，确保 TaskInfo、ContextPacket、"
        "Rubric、Subtask、ThoughtState、Score、Aggregation、Validation 和 Trace 都能形成闭环。"
    )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?\n]+", text)
    return [part.strip(" -\t") for part in parts if part.strip(" -\t")]


def _summarize(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _infer_claim_type(sentence: str) -> str:
    if _contains_any(sentence, ["建议", "应该", "先", "recommend"]):
        return "recommendation"
    if _contains_any(sentence, ["风险", "失败", "risk"]):
        return "risk"
    if _contains_any(sentence, ["假设", "assume"]):
        return "assumption"
    return "reasoning"


def _detect_risks(text: str) -> list[str]:
    risks = []
    if len(text) < 80:
        risks.append("候选内容较短，可能缺少完整工程细节。")
    if not _contains_any(text, ["trace", "Trace"]):
        risks.append("候选内容可能没有覆盖 trace 记录。")
    return risks


def _score_state(state: ThoughtState, user_query: str, weights: dict[str, float]) -> Score:
    draft = state.draft or ""
    overlap = _keyword_overlap(user_query, draft)
    score = Score(
        correctness=0.78,
        completeness=min(0.95, 0.55 + 0.05 * len(state.claims)),
        relevance=min(0.98, 0.72 + overlap),
        clarity=0.82 if "\n" in draft else 0.70,
        groundedness=0.68 if state.assumptions else 0.55,
        safety=1.0,
        novelty=0.50,
        actionability=0.84 if _contains_any(draft, ["建议", "确保", "实现", "trace", "pipeline"]) else 0.62,
        notes=[],
    )
    if weights:
        score.recompute_overall(weights)
    else:
        score.overall = (
            score.correctness
            + score.completeness
            + score.relevance
            + score.clarity
            + score.groundedness
            + score.safety
            + score.actionability
        ) / 7
    return score


def _keyword_overlap(query: str, draft: str) -> float:
    query_terms = {term for term in re.split(r"\W+", query.lower()) if len(term) >= 3}
    draft_terms = {term for term in re.split(r"\W+", draft.lower()) if len(term) >= 3}
    if not query_terms:
        return 0.0
    return min(0.22, len(query_terms & draft_terms) / max(1, len(query_terms)) * 0.22)


def _critique_from_score(score: Score) -> list[str]:
    critique: list[str] = []
    if score.completeness < 0.78:
        critique.append("完整度不足：需要补充验收标准和边界。")
    if score.groundedness < 0.70:
        critique.append("groundedness 偏低：需要更明确地绑定上下文和 trace。")
    if score.actionability < 0.75:
        critique.append("可执行性不足：需要更具体的实现步骤。")
    return critique


def _deduplicate_claims(claims: list[Claim]) -> list[Claim]:
    seen: set[str] = set()
    unique: list[Claim] = []
    for claim in claims:
        key = claim.text.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(claim)
    return unique[:12]


def _aggregate_draft(user_query: str, states: list[ThoughtState], claims: list[Claim]) -> str:
    selected = ", ".join(state.id for state in states)
    claim_lines = "\n".join(f"- {claim.text}" for claim in claims[:8])
    return (
        "# Pipeline v0.2 聚合结果\n\n"
        f"用户请求：{user_query}\n\n"
        "本次 mock runner 已经跑通从 task intake 到 final validation 的完整闭环。"
        "当前重点不是生成最终生产答案，而是验证 thought-state orchestration 的工程数据流。\n\n"
        "## 已选择的高价值 claims\n"
        f"{claim_lines}\n\n"
        "## v0.2 交付物\n"
        "- Prompter 契约与默认 prompt templates\n"
        "- JSON parser / repair 基础工具\n"
        "- deterministic mock operators\n"
        "- trace JSONL 持久化\n"
        "- demo CLI：`python -m tsgo.demo \"你的问题\"`\n\n"
        "## 下一步\n"
        "进入 v0.3 时，将 mock operators 替换为真实 LLM-backed operators，并保持同一套 "
        "ThoughtState / OperatorResult / Trace 契约。\n\n"
        f"聚合来源 states：{selected}\n"
    )

"""SecondaryMarketAnalyst stage-flow Operators.

This module turns the documented SecondaryMarketAnalyst stage instructions into
a runnable deterministic stage flow. The goal is to exercise the full
ThoughtGraph -> GraphController -> Operator -> ThoughtState path before adding
more sophisticated Operator implementations.
"""

from __future__ import annotations

from typing import Any

from ..operators import Operator, OperatorResult
from ..schema import (
    Claim,
    ContextPacket,
    Rubric,
    RubricItem,
    Score,
    Subtask,
    TaskInfo,
    ThoughtState,
    Trace,
    new_state_id,
)


EXPERT_PROFILE = "SecondaryMarketAnalyst"

BRANCH_TYPES = [
    "bull_case",
    "bear_case",
    "base_case",
    "technical_flow",
    "catalyst_driven",
    "risk_first",
]

STAGE_PROMPT_IDS = {
    "task_intake": "secondary_market.prompt.01.task_intake",
    "context_builder": "secondary_market.prompt.02.context_builder",
    "rubric_builder": "secondary_market.prompt.03.rubric_builder",
    "problem_decomposer": "secondary_market.prompt.04.problem_decomposer",
    "candidate_generator": "secondary_market.prompt.05.candidate_generator",
    "thought_normalizer": "secondary_market.prompt.06.thought_normalizer",
    "verifier_scorer": "secondary_market.prompt.07.verifier_scorer",
    "improver": "secondary_market.prompt.08.improver",
    "aggregator": "secondary_market.prompt.09.aggregator",
    "final_validator": "secondary_market.prompt.10.final_validator",
}


class SecondaryMarketTaskIntakeOperator(Operator):
    """Expert handoff + task intake for secondary market analysis."""

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
        asset = _infer_asset(user_query)
        horizon = _infer_time_horizon(user_query)
        required_fresh = _contains_any(
            user_query,
            ["今天", "现在", "实时", "走势", "price", "today", "latest", "current"],
        )
        missing = []
        if asset == "unknown":
            missing.append("标的")
        if horizon == "unknown":
            missing.append("时间周期")

        trace.task_info = TaskInfo(
            user_query=user_query,
            task_type="research",
            difficulty="high",
            requires_tools=required_fresh,
            requires_citations=False,
            requires_computation=False,
            requires_user_context=False,
            answer_format="secondary_market_analysis",
            metadata={
                "expert_profile": EXPERT_PROFILE,
                "asset_or_market": asset,
                "market_type": _infer_market_type(user_query),
                "user_intent": "market_analysis",
                "time_horizon": horizon,
                "geography": _infer_geography(user_query),
                "required_fresh_data": required_fresh,
                "missing_context": missing,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
            },
        )

        handoff = {
            "selected_expert": EXPERT_PROFILE,
            "handoff_reason": "用户请求涉及二级市场分析，需要市场结构、估值、技术面、资金流、催化和风险框架。",
            "asset_or_market": asset,
            "time_horizon": horizon,
            "user_intent": "market_analysis",
            "missing_context": missing,
            "compliance_constraints": [
                "不得提供个性化投资建议",
                "必须区分事实、假设和推断",
                "必须给出风险和失效条件",
            ],
        }
        trace.metadata["expert_profile"] = EXPERT_PROFILE
        trace.metadata["expert_handoff"] = handoff
        return OperatorResult(
            logs=[f"已 handoff 到 {EXPERT_PROFILE}。"],
            metadata={"expert_handoff": handoff, "prompt_id": STAGE_PROMPT_IDS[self.name]},
        )


class SecondaryMarketContextBuilderOperator(Operator):
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
        task_meta = trace.task_info.metadata if trace.task_info else {}
        asset = str(task_meta.get("asset_or_market", "unknown"))
        horizon = str(task_meta.get("time_horizon", "unknown"))
        required_fresh = bool(task_meta.get("required_fresh_data", False))
        price_context = "unavailable_without_market_data" if required_fresh else "unknown"
        missing_data = ["实时价格", "成交量", "资金流", "最新新闻"] if required_fresh else []

        trace.context = ContextPacket(
            user_intent="secondary_market_analysis",
            hard_constraints=[
                "不得提供个性化投资建议",
                "不得伪造实时市场数据",
                "必须区分 facts / assumptions / interpretations",
            ],
            soft_preferences=["覆盖 bull/base/bear 情景", "给出风险和失效条件"],
            available_context=[
                f"asset_identity={asset}",
                f"time_horizon={horizon}",
                f"price_context={price_context}",
            ],
            missing_context=list(task_meta.get("missing_context", [])) + missing_data,
            retrieved_evidence=[],
            tool_plan=[],
            metadata={
                "expert_profile": EXPERT_PROFILE,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "market_context": {
                    "asset_identity": asset,
                    "macro_context": "unknown",
                    "fundamental_context": "unknown",
                    "price_context": price_context,
                    "flow_context": "unknown",
                    "catalyst_context": "unknown",
                    "risk_context": "需要识别下行风险、反向催化、流动性风险和拥挤交易风险。",
                    "missing_data": missing_data,
                },
            },
        )
        return OperatorResult(logs=["已构建 SecondaryMarketAnalyst ContextPacket。"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketRubricBuilderOperator(Operator):
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
        trace.rubric = Rubric(
            items=[
                RubricItem("correctness", 0.22, "事实和数据是否准确。", 0.75),
                RubricItem("groundedness", 0.16, "证据强度和数据新鲜度。", 0.70),
                RubricItem("relevance", 0.14, "因果链和用户问题相关性。", 0.75),
                RubricItem("completeness", 0.14, "是否覆盖 bull/base/bear 情景。", 0.75),
                RubricItem("safety", 0.14, "是否识别风险并避免个性化建议。", 0.95),
                RubricItem("actionability", 0.08, "是否可用于研究决策但不构成建议。", 0.70),
                RubricItem("clarity", 0.06, "结构是否清晰。", 0.70),
                RubricItem("novelty", 0.06, "是否提供非同质化视角。", 0.50),
            ],
            hard_constraints=trace.context.hard_constraints if trace.context else [],
            soft_preferences=trace.context.soft_preferences if trace.context else [],
        )
        trace.rubric.hard_constraints.extend([
            "禁止伪造实时市场数据",
            "禁止直接给出个性化买入/卖出/持有建议",
        ])
        return OperatorResult(logs=["已构建二级市场分析 rubric。"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketProblemDecomposerOperator(Operator):
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
        task_type = trace.task_info.task_type if trace.task_info else "research"
        trace.subtasks = [
            Subtask(
                id="s1",
                question="当前标的处于什么市场环境和风险偏好背景？",
                task_type=task_type,
                required_outputs=["market_regime", "macro_variables", "risk_appetite"],
                dependencies=[],
                metadata={"evidence_needed": ["index performance", "rates", "volatility"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
            Subtask(
                id="s2",
                question="基本面和估值是否支持当前价格叙事？",
                task_type=task_type,
                required_outputs=["valuation_context", "earnings_trend", "sector_comparison"],
                dependencies=["s1"],
                metadata={"evidence_needed": ["financials", "multiples", "guidance"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
            Subtask(
                id="s3",
                question="技术面、趋势和关键价位如何影响情景判断？",
                task_type=task_type,
                required_outputs=["trend", "levels", "volatility"],
                dependencies=["s1"],
                metadata={"evidence_needed": ["price series", "volume", "volatility"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
            Subtask(
                id="s4",
                question="成交量、资金流、持仓和情绪是否支持当前叙事？",
                task_type=task_type,
                required_outputs=["flow_context", "positioning", "sentiment"],
                dependencies=["s1"],
                metadata={"evidence_needed": ["volume", "fund flow", "options"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
            Subtask(
                id="s5",
                question="未来催化剂、风险和失效条件是什么？",
                task_type=task_type,
                required_outputs=["catalysts", "risks", "invalidation_conditions"],
                dependencies=["s2", "s3", "s4"],
                metadata={"evidence_needed": ["earnings calendar", "macro calendar", "news"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
            Subtask(
                id="s6",
                question="如何形成 bull/base/bear 三情景并标注数据缺口？",
                task_type=task_type,
                required_outputs=["bull_case", "base_case", "bear_case", "data_gaps"],
                dependencies=["s1", "s2", "s3", "s4", "s5"],
                metadata={"evidence_needed": ["all previous subtasks"], "prompt_id": STAGE_PROMPT_IDS[self.name]},
            ),
        ]
        return OperatorResult(logs=[f"已拆解为 {len(trace.subtasks)} 个二级市场分析 subtasks。"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketCandidateGeneratorOperator(Operator):
    name = "candidate_generator"

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
        branch_count = min(int(getattr(config, "default_num_branches", 6)), len(BRANCH_TYPES))
        branches = BRANCH_TYPES[:branch_count]
        generated: list[ThoughtState] = []
        for item in trace.subtasks:
            for branch_index, branch_type in enumerate(branches):
                draft = _candidate_draft(user_query, item, branch_type)
                generated.append(
                    ThoughtState(
                        id=new_state_id("candidate"),
                        parent_ids=[item.id],
                        stage="candidate_generator",
                        user_query=user_query,
                        task_type=item.task_type,
                        draft=draft,
                        summary=f"{branch_type} for {item.id}",
                        status="draft",
                        assumptions=["没有实时行情工具时，所有价格/资金流相关内容必须标记为 data_required。"],
                        metadata={
                            "expert_profile": EXPERT_PROFILE,
                            "prompt_id": STAGE_PROMPT_IDS[self.name],
                            "branch_type": branch_type,
                            "generation_strategy": branch_type,
                            "branch_index": branch_index,
                            "subtask_id": item.id,
                            "evidence_needed": item.metadata.get("evidence_needed", []),
                            "invalidation_conditions": ["关键假设被实时数据或新事件证伪。"],
                            "risks": ["数据缺口导致结论置信度下降。"],
                        },
                    )
                )
        return OperatorResult(new_states=generated, logs=[f"生成二级市场候选分支数量：{len(generated)}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketThoughtNormalizerOperator(Operator):
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
            branch_type = str(state.metadata.get("branch_type", "base_case"))
            subtask_id = str(state.metadata.get("subtask_id", "unknown"))
            claims = [
                Claim(
                    text=f"{subtask_id} 的 {branch_type} 分支依赖显式假设和待验证证据。",
                    claim_type="reasoning",
                    confidence=0.74,
                    metadata={"evidence_status": "missing", "data_freshness_required": True},
                ),
                Claim(
                    text="如果缺少实时行情或资金流数据，相关判断必须降级为 assumption。",
                    claim_type="risk",
                    confidence=0.9,
                    metadata={"evidence_status": "supported", "data_freshness_required": False},
                ),
            ]
            normalized.append(
                _clone_state(
                    state,
                    prefix="normalized",
                    stage="thought_normalizer",
                    status="normalized",
                    summary=f"规范化 {subtask_id} / {branch_type}。",
                    claims=claims,
                    assumptions=list(state.assumptions),
                    missing_info=list(state.metadata.get("evidence_needed", [])),
                    failure_modes=list(state.metadata.get("risks", [])),
                    metadata={
                        **state.metadata,
                        "prompt_id": STAGE_PROMPT_IDS[self.name],
                        "market_variables": ["price", "volume", "volatility", "fund_flow", "catalysts"],
                        "risk_items": state.metadata.get("risks", []),
                    },
                )
            )
        return OperatorResult(new_states=normalized, logs=[f"规范化二级市场 ThoughtStates 数量：{len(normalized)}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketVerifierScorerOperator(Operator):
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
        weights = trace.rubric.weight_map() if trace.rubric else {}
        scored: list[ThoughtState] = []
        for state in states:
            branch_type = str(state.metadata.get("branch_type", "base_case"))
            score = Score(
                correctness=0.82,
                completeness=0.82 if branch_type in {"bull_case", "bear_case", "base_case"} else 0.76,
                relevance=0.9,
                clarity=0.84,
                groundedness=0.72,
                safety=1.0,
                novelty=0.78 if branch_type in {"technical_flow", "catalyst_driven", "risk_first"} else 0.66,
                actionability=0.78,
                notes=["secondary_market_stage_flow"],
            )
            score.recompute_overall(weights)
            critique = []
            if "实时价格" in state.missing_info:
                critique.append("价格相关判断需要实时数据验证。")
            if branch_type != "risk_first":
                critique.append("需要保留风险和失效条件。")
            scored.append(
                _clone_state(
                    state,
                    prefix="scored",
                    stage="verifier_scorer",
                    status="scored",
                    score=score,
                    critique=critique,
                    metadata={**state.metadata, "prompt_id": STAGE_PROMPT_IDS[self.name], "decision": "aggregate"},
                )
            )
        return OperatorResult(new_states=scored, logs=[f"评分二级市场 ThoughtStates 数量：{len(scored)}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketImproverOperator(Operator):
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
        improved: list[ThoughtState] = []
        for state in states:
            if not state.score or state.score.overall >= 0.80:
                continue
            repaired = f"{state.draft}\n\n修复：补充风险、失效条件，并将实时数据依赖标记为 data_required。"
            improved.append(
                _clone_state(
                    state,
                    prefix="improved",
                    stage="improver",
                    status="improved",
                    draft=repaired,
                    critique=["已按 verifier feedback 补充风险和数据缺口。"],
                    metadata={**state.metadata, "prompt_id": STAGE_PROMPT_IDS[self.name], "improvement_round": 1},
                )
            )
        return OperatorResult(new_states=improved, logs=[f"改进二级市场 ThoughtStates 数量：{len(improved)}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketAggregatorOperator(Operator):
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
        pool = [state for state in trace.states if state.status in {"scored", "improved"} and state.score]
        selected = _select_diverse(pool)
        if not selected:
            return OperatorResult(errors=["没有可聚合的二级市场 ThoughtState。"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})
        selected_subtasks = sorted({str(state.metadata.get("subtask_id")) for state in selected})
        selected_branches = sorted({str(state.metadata.get("branch_type")) for state in selected})
        draft = _aggregate_draft(user_query, selected_subtasks, selected_branches, trace)
        claims = [
            Claim(
                text="最终输出应以 bull/base/bear 情景和失效条件表达，不构成个性化投资建议。",
                claim_type="recommendation",
                confidence=0.92,
            )
        ]
        aggregated = ThoughtState(
            id=new_state_id("aggregated"),
            parent_ids=[state.id for state in selected],
            stage="aggregator",
            user_query=user_query,
            task_type="research",
            draft=draft,
            summary="二级市场分析聚合结果。",
            claims=claims,
            assumptions=["没有实时市场数据时，价格、资金流和新闻相关结论必须保持低置信度。"],
            missing_info=trace.context.missing_context if trace.context else [],
            score=selected[0].score,
            status="aggregated",
            metadata={
                "expert_profile": EXPERT_PROFILE,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "aggregation_policy": "secondary_market_diversity_aware_claim_level_merge",
                "selected_state_ids": [state.id for state in selected],
                "selected_subtask_ids": selected_subtasks,
                "selected_branch_types": selected_branches,
                "conflicts_and_resolutions": [],
            },
        )
        return OperatorResult(new_states=[aggregated], logs=[f"聚合二级市场 states 数量：{len(selected)}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


class SecondaryMarketFinalValidatorOperator(Operator):
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
            return OperatorResult(errors=["没有可验证的 aggregated state。"])
        state = states[-1]
        draft = state.draft or ""
        blocking = []
        for required in ["Bull", "Base", "Bear", "风险", "数据缺口", "不是个性化投资建议"]:
            if required not in draft:
                blocking.append(f"最终答案缺少：{required}")
        passed = not blocking
        validated = _clone_state(
            state,
            prefix="validated" if passed else "rejected",
            stage="final_validator",
            status="validated" if passed else "rejected",
            metadata={
                **state.metadata,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "validation": {
                    "pass": passed,
                    "blocking_issues": blocking,
                    "required_edits": blocking,
                    "confidence": 0.88 if passed else 0.35,
                    "final_release_notes": ["该输出是二级市场研究框架，不是个性化投资建议。"],
                },
            },
        )
        return OperatorResult(new_states=[validated], errors=[] if passed else blocking, logs=[f"二级市场最终验证 pass={passed}"], metadata={"prompt_id": STAGE_PROMPT_IDS[self.name]})


def build_secondary_market_operators() -> dict[str, Operator]:
    """Return a complete Stage-flow Operator set for SecondaryMarketAnalyst."""

    return {
        "task_intake": SecondaryMarketTaskIntakeOperator(),
        "context_builder": SecondaryMarketContextBuilderOperator(),
        "rubric_builder": SecondaryMarketRubricBuilderOperator(),
        "problem_decomposer": SecondaryMarketProblemDecomposerOperator(),
        "candidate_generator": SecondaryMarketCandidateGeneratorOperator(),
        "thought_normalizer": SecondaryMarketThoughtNormalizerOperator(),
        "verifier_scorer": SecondaryMarketVerifierScorerOperator(),
        "improver": SecondaryMarketImproverOperator(),
        "aggregator": SecondaryMarketAggregatorOperator(),
        "final_validator": SecondaryMarketFinalValidatorOperator(),
    }


def _candidate_draft(user_query: str, subtask: Subtask, branch_type: str) -> str:
    return (
        f"branch_type: {branch_type}\n"
        f"subtask: {subtask.id} - {subtask.question}\n"
        f"user_query: {user_query}\n\n"
        "thesis: 在该分支假设下构造一个可验证的二级市场分析路径。\n"
        "supporting_claims: 需要结合市场环境、价格行为、资金流、催化剂和风险验证。\n"
        "assumptions: 如果没有实时数据，不对价格、估值、资金流作事实断言。\n"
        "evidence_needed: 使用 subtask 指定证据。\n"
        "invalidation_conditions: 关键假设被新数据或新事件证伪。\n"
        "risks: 数据缺口、流动性、波动率和反向催化。\n"
        "confidence: medium。\n"
    )


def _aggregate_draft(user_query: str, subtasks: list[str], branches: list[str], trace: Trace) -> str:
    asset = trace.task_info.metadata.get("asset_or_market", "unknown") if trace.task_info else "unknown"
    horizon = trace.task_info.metadata.get("time_horizon", "unknown") if trace.task_info else "unknown"
    data_gaps = trace.context.missing_context if trace.context else []
    return (
        "# 二级市场分析聚合结果\n\n"
        "声明：以下内容是研究框架，不是个性化投资建议，不构成买入、卖出或持有建议。\n\n"
        f"用户请求：{user_query}\n"
        f"标的/市场：{asset}\n"
        f"时间周期：{horizon}\n"
        f"覆盖 subtasks：{', '.join(subtasks)}\n"
        f"覆盖分支：{', '.join(branches)}\n\n"
        "## 结论摘要\n"
        "当前应以情景框架而不是单点结论表达：在关键假设成立时，Bull/Base/Bear 三条路径分别对应风险偏好改善、基准震荡等待催化、以及反向催化或估值压缩。\n\n"
        "## Bull 情景\n"
        "驱动因素：风险偏好改善、基本面预期上修、资金流改善或正向催化。\n"
        "触发条件：需要实时价格、成交量、新闻和财务数据验证。\n"
        "失效条件：关键价位失守、盈利预期下修、风险偏好恶化。\n\n"
        "## Base 情景\n"
        "驱动因素：市场维持当前定价，等待新催化或数据确认。\n"
        "触发条件：价格和成交量缺乏方向性突破。\n"
        "失效条件：出现明确的基本面或流动性冲击。\n\n"
        "## Bear 情景\n"
        "驱动因素：估值压缩、负面催化、流动性收缩、拥挤交易出清。\n"
        "触发条件：风险资产回撤、成交量放大下跌、负面事件出现。\n"
        "失效条件：风险偏好修复或基本面数据超预期。\n\n"
        "## 风险\n"
        "主要风险包括数据缺口、实时行情不可用、流动性变化、波动率扩张、反向政策或公司事件。\n\n"
        "## 数据缺口\n"
        f"{', '.join(data_gaps) if data_gaps else '当前未接实时数据工具，价格和资金流相关内容仍需验证。'}\n\n"
        "## 下一步需要验证\n"
        "实时价格、成交量、波动率、财报/估值、行业比较、资金流、新闻催化和宏观变量。\n"
    )


def _select_diverse(states: list[ThoughtState]) -> list[ThoughtState]:
    sorted_states = sorted(states, key=lambda state: state.score.overall if state.score else 0.0, reverse=True)
    selected: list[ThoughtState] = []
    seen_subtasks: set[str] = set()
    for state in sorted_states:
        subtask_id = str(state.metadata.get("subtask_id", "unknown"))
        if subtask_id not in seen_subtasks:
            selected.append(state)
            seen_subtasks.add(subtask_id)
    seen_branches = {str(state.metadata.get("branch_type", "unknown")) for state in selected}
    for state in sorted_states:
        branch = str(state.metadata.get("branch_type", "unknown"))
        if branch not in seen_branches:
            selected.append(state)
            seen_branches.add(branch)
        if len(selected) >= 12:
            break
    return selected


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


def _infer_asset(query: str) -> str:
    tokens = query.replace("，", " ").replace(",", " ").split()
    for token in tokens:
        cleaned = token.strip().upper().strip("。！？!?:：")
        if 1 <= len(cleaned) <= 8 and cleaned.isascii() and any(char.isalpha() for char in cleaned):
            return cleaned
    return "unknown"


def _infer_market_type(query: str) -> str:
    if _contains_any(query, ["ETF", "etf"]):
        return "ETF"
    if _contains_any(query, ["指数", "index"]):
        return "index"
    if _contains_any(query, ["币", "crypto", "BTC", "ETH"]):
        return "crypto"
    if _infer_asset(query) != "unknown":
        return "equity"
    return "unknown"


def _infer_time_horizon(query: str) -> str:
    if _contains_any(query, ["日内", "今天", "intraday"]):
        return "intraday"
    if _contains_any(query, ["短线", "一周", "short"]):
        return "short_term"
    if _contains_any(query, ["波段", "swing"]):
        return "swing"
    if _contains_any(query, ["中期", "季度", "medium"]):
        return "medium_term"
    if _contains_any(query, ["长期", "long"]):
        return "long_term"
    return "unknown"


def _infer_geography(query: str) -> str:
    if _contains_any(query, ["美股", "nasdaq", "nyse", "US", "美国"]):
        return "US"
    if _contains_any(query, ["A股", "沪", "深", "中国"]):
        return "CN"
    if _contains_any(query, ["港股", "香港"]):
        return "HK"
    return "unknown"


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)

"""Prompter contracts for Pipeline v0.3.

Prompters only build prompt strings. They do not own orchestration, state IDs,
branching policy, retry policy, validation gates, or trace persistence.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class Prompter(ABC):
    """Abstract prompt-construction interface used by pipeline operators."""

    @abstractmethod
    def generate_prompt(self, num_branches: int, **kwargs: Any) -> str:
        """Build a prompt that asks the model to generate candidate branches."""

    @abstractmethod
    def score_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        """Build a prompt that asks the model to score thought states."""

    @abstractmethod
    def improve_prompt(self, **kwargs: Any) -> str:
        """Build a prompt that asks the model to repair a flawed thought state."""

    @abstractmethod
    def aggregation_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        """Build a prompt that asks the model to aggregate multiple thought states."""

    @abstractmethod
    def validation_prompt(self, **kwargs: Any) -> str:
        """Build a prompt that asks the model to validate the final state."""


class DefaultPipelinePrompter(Prompter):
    """Chinese prompt templates with explicit JSON-contract expectations."""

    def generate_prompt(self, num_branches: int, **kwargs: Any) -> str:
        user_query = kwargs.get("user_query", "")
        context = kwargs.get("context", None)
        rubric = kwargs.get("rubric", None)
        subtask = kwargs.get("subtask", None)
        strategy = kwargs.get("strategy", "direct")
        return (
            "你是 Pipeline v0.3 的 Candidate Generator。\n"
            "你的任务是生成候选 ThoughtState draft，不要评分、不要聚合。\n"
            f"用户请求：{user_query}\n"
            f"子任务：{getattr(subtask, 'question', subtask)}\n"
            f"生成策略：{strategy}\n"
            f"Context：{_jsonable(context)}\n"
            f"Rubric：{_jsonable(rubric)}\n"
            f"请生成 {num_branches} 个互补候选。\n"
            "必须只返回 JSON：{\"branches\": [{\"draft\": \"...\"}]}"
        )

    def score_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        context = kwargs.get("context", None)
        rubric = kwargs.get("rubric", None)
        return (
            "你是 Pipeline v0.3 的 Verifier / Scorer。\n"
            "请根据下面提供的 ThoughtStates 原文、claims、assumptions、missing_info 和 rubric 评分。\n"
            "不要说没有输入；待评分对象已经在 ThoughtStates JSON 中提供。\n"
            "请按 correctness、completeness、relevance、clarity、groundedness、"
            "safety、actionability、overall 为每个 ThoughtState 打 0..1 分。\n"
            "如果存在个性化投资建议、伪造实时数据、缺少风险/失效条件，必须写入 critical_errors。\n"
            f"Context：{_jsonable(context)}\n"
            f"Rubric：{_jsonable(rubric)}\n"
            f"ThoughtStates：{_jsonable(state_dicts)}\n"
            "必须只返回 JSON：{\"scores\": [{\"state_id\": \"...\", \"correctness\": 0.0, "
            "\"completeness\": 0.0, \"relevance\": 0.0, \"clarity\": 0.0, "
            "\"groundedness\": 0.0, \"safety\": 1.0, \"actionability\": 0.0, "
            "\"overall\": 0.0, \"strengths\": [], \"weaknesses\": [], "
            "\"critical_errors\": [], \"improvement_instructions\": []}]}"
        )

    def improve_prompt(self, **kwargs: Any) -> str:
        state = kwargs.get("state", {})
        critique = kwargs.get("critique", [])
        context = kwargs.get("context", None)
        rubric = kwargs.get("rubric", None)
        return (
            "你是 Pipeline v0.3 的 Improver。\n"
            "请基于 verifier critique 修复下面的 ThoughtState。\n"
            "不要自由重写；只修复 verifier 指出的具体问题。\n"
            "保留正确内容，删除无依据 claim，不引入未验证新断言。\n"
            f"Context：{_jsonable(context)}\n"
            f"Rubric：{_jsonable(rubric)}\n"
            f"State：{_jsonable(state)}\n"
            f"Critique：{_jsonable(critique)}\n"
            "必须只返回 JSON：{\"draft\": \"...\", \"change_summary\": [], "
            "\"removed_claims\": [], \"added_claims\": []}"
        )

    def aggregation_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        context = kwargs.get("context", None)
        rubric = kwargs.get("rubric", None)
        aggregation_policy = kwargs.get("aggregation_policy", "diversity_aware_claim_level_merge")
        return (
            "你是 Pipeline v0.3 的 Aggregator。\n"
            "请聚合下面提供的 top ThoughtStates。聚合不是拼接，而是按 claim、scenario 和 evidence strength 综合。\n"
            "必须覆盖不同 subtask / branch 的高质量内容，显式记录冲突和裁决理由。\n"
            "最终答案不能包含个性化投资建议。\n"
            f"Context：{_jsonable(context)}\n"
            f"Rubric：{_jsonable(rubric)}\n"
            f"AggregationPolicy：{aggregation_policy}\n"
            f"StatesToAggregate：{_jsonable(state_dicts)}\n"
            "必须只返回 JSON：{\"draft\": \"...\", \"selected_claims\": [], "
            "\"conflicts\": [], \"resolutions\": [], "
            "\"aggregation_policy\": \"diversity_aware_claim_level_merge\"}"
        )

    def validation_prompt(self, **kwargs: Any) -> str:
        state = kwargs.get("state", {})
        user_query = kwargs.get("user_query", "")
        context = kwargs.get("context", None)
        rubric = kwargs.get("rubric", None)
        return (
            "你是 Pipeline v0.3 的 Final Validator。\n"
            "请验证下面的最终 State 是否可以发布。不要说没有输入；待验证对象已经在 State JSON 中提供。\n"
            "检查是否回答用户请求、是否满足硬约束、安全要求和可执行性。\n"
            "如果存在个性化投资建议、伪造实时数据、缺少风险/失效条件，必须 pass=false。\n"
            f"用户请求：{user_query}\n"
            f"Context：{_jsonable(context)}\n"
            f"Rubric：{_jsonable(rubric)}\n"
            f"State：{_jsonable(state)}\n"
            "必须只返回 JSON：{\"pass\": true, \"blocking_issues\": [], "
            "\"non_blocking_issues\": [], \"required_edits\": [], \"confidence\": 0.0}"
        )


def _jsonable(value: Any) -> str:
    if value is None:
        return "null"
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)

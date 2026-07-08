"""Prompter contracts for Pipeline v0.2.

Prompters only build prompt strings. They do not own orchestration, state IDs,
branching policy, retry policy, validation gates, or trace persistence.
"""

from __future__ import annotations

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
    """Chinese prompt templates with explicit JSON-contract expectations.

    The mock v0.2 pipeline does not require an LLM, but these templates define
    the contracts that a future LLM-backed operator should use.
    """

    def generate_prompt(self, num_branches: int, **kwargs: Any) -> str:
        user_query = kwargs.get("user_query", "")
        subtask = kwargs.get("subtask", None)
        strategy = kwargs.get("strategy", "direct")
        return (
            "你是 Pipeline v0.2 的 Candidate Generator。\n"
            f"用户请求：{user_query}\n"
            f"子任务：{getattr(subtask, 'question', subtask)}\n"
            f"生成策略：{strategy}\n"
            f"请生成 {num_branches} 个互补候选。\n"
            "返回 JSON：{\"branches\": [{\"draft\": \"...\"}]}"
        )

    def score_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        return (
            "你是 Pipeline v0.2 的 Verifier / Scorer。\n"
            "请按 correctness、completeness、relevance、clarity、groundedness、"
            "safety、actionability、overall 为每个 ThoughtState 打 0..1 分。\n"
            f"待评分状态数量：{len(state_dicts)}\n"
            "返回 JSON：{\"scores\": [{\"state_id\": \"...\", \"overall\": 0.0, "
            "\"weaknesses\": [], \"critical_errors\": []}]}"
        )

    def improve_prompt(self, **kwargs: Any) -> str:
        return (
            "你是 Pipeline v0.2 的 Improver。\n"
            "不要自由重写；只修复 verifier 指出的具体问题。\n"
            "保留正确内容，删除无依据 claim，不引入未验证新断言。\n"
            "返回 JSON：{\"draft\": \"...\", \"change_summary\": []}"
        )

    def aggregation_prompt(self, state_dicts: list[dict[str, Any]], **kwargs: Any) -> str:
        return (
            "你是 Pipeline v0.2 的 Aggregator。\n"
            f"需要聚合的状态数量：{len(state_dicts)}\n"
            "请按 claim 粒度合并，显式记录冲突和裁决理由。\n"
            "返回 JSON：{\"draft\": \"...\", \"selected_claims\": [], "
            "\"conflicts\": [], \"resolutions\": []}"
        )

    def validation_prompt(self, **kwargs: Any) -> str:
        return (
            "你是 Pipeline v0.2 的 Final Validator。\n"
            "判断最终答案是否满足用户请求、硬约束、安全要求和可执行性。\n"
            "返回 JSON：{\"pass\": true, \"blocking_issues\": [], "
            "\"required_edits\": [], \"confidence\": 0.0}"
        )

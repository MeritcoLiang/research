"""Instruction-driven expert handoff routing.

OpenAI Agents SDK handoffs are not just graph labels. They are exposed to the
router model as target-specific tools, and invoking a handoff transfers control
to the chosen specialist. This module keeps that contract explicit for the
SecondaryMarketAnalyst flow before the project adopts the Agents SDK directly.
"""

from __future__ import annotations

import json
from typing import Any

from ..model_client import ModelClient
from ..operators import Operator, OperatorResult
from ..schema import ContextPacket, Rubric, Subtask, TaskInfo, ThoughtState, Trace
from .secondary_market import (
    EXPERT_PROFILE,
    STAGE_PROMPT_IDS,
    _contains_any,
    _infer_asset,
    _infer_geography,
    _infer_market_type,
    _infer_time_horizon,
)

EXPERT_ROUTER_AGENT = "ExpertRouter"
HANDOFF_TOOL_NAME = "transfer_to_secondary_market_analyst"
HANDOFF_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reason": {"type": "string"},
        "asset_or_market": {"type": "string"},
        "time_horizon": {"type": "string"},
        "user_intent": {"type": "string"},
        "missing_context": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reason", "asset_or_market", "time_horizon", "user_intent", "missing_context"],
}
HANDOFF_DESCRIPTION = (
    "Use this handoff when the user asks for secondary-market analysis, trading context, "
    "valuation/risk/catalyst framing, market structure, price/volume/flow interpretation, "
    "or bull/base/bear scenario work."
)
EXPERT_ROUTER_INSTRUCTIONS = f"""
You are {EXPERT_ROUTER_AGENT}. Your job is routing, not answering.

Available handoff tools:
- {HANDOFF_TOOL_NAME}: {HANDOFF_DESCRIPTION}

Rules:
1. Read the user message and decide whether a specialist should take over.
2. For secondary-market analysis, call {HANDOFF_TOOL_NAME}; do not answer the user directly.
3. The handoff call must include structured metadata: reason, asset_or_market,
   time_horizon, user_intent, and missing_context.
4. After the handoff is invoked, {EXPERT_PROFILE} owns the rest of the turn and
   must run the domain-specific stage flow.
5. If required market data is unavailable, route anyway but mark the missing data
   explicitly; the specialist must not fabricate real-time prices, flows, or news.

Return only JSON in this shape:
{{
  "tool_name": "{HANDOFF_TOOL_NAME}",
  "selected_expert": "{EXPERT_PROFILE}",
  "reason": "why this handoff should be invoked",
  "asset_or_market": "ticker, asset, market, or unknown",
  "time_horizon": "intraday | short_term | swing | medium_term | long_term | unknown",
  "user_intent": "market_analysis",
  "missing_context": ["..."]
}}
""".strip()
SECONDARY_MARKET_ANALYST_INSTRUCTIONS = """
You are SecondaryMarketAnalyst. You take over after ExpertRouter invokes the
transfer_to_secondary_market_analyst handoff. Run the secondary-market stage flow
and produce a research framework, not personalized investment advice.

You must:
- separate facts, assumptions, and interpretations;
- cover market regime, fundamentals/valuation, technicals, flows, catalysts,
  risks, and invalidation conditions;
- build bull/base/bear scenarios;
- mark real-time price, volume, flow, and news requirements as data gaps unless
  tool evidence is actually available;
- preserve the user's original message and handoff metadata in every downstream
  Operator context.
""".strip()


class SecondaryMarketLLMExpertRouterOperator(Operator):
    """LLM-backed ExpertRouter that invokes a target-specific handoff tool."""

    name = "task_intake"

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
        inferred = _infer_routing_context(user_query)
        prompt = build_expert_router_prompt(user_query=user_query, inferred=inferred)
        raw = self.model_client.generate(prompt)
        packet, parse_error = _parse_router_packet(raw)
        handoff = build_secondary_market_handoff(
            user_query=user_query,
            inferred=inferred,
            packet=packet,
            prompt=prompt,
            raw_model_output=raw,
            parse_error=parse_error,
        )

        trace.task_info = TaskInfo(
            user_query=user_query,
            task_type="research",
            difficulty="high",
            requires_tools=bool(inferred["required_fresh_data"]),
            requires_citations=False,
            requires_computation=False,
            requires_user_context=False,
            answer_format="secondary_market_analysis",
            metadata={
                "expert_profile": EXPERT_PROFILE,
                "asset_or_market": handoff["asset_or_market"],
                "market_type": inferred["market_type"],
                "user_intent": handoff["user_intent"],
                "time_horizon": handoff["time_horizon"],
                "geography": inferred["geography"],
                "required_fresh_data": inferred["required_fresh_data"],
                "missing_context": handoff["missing_context"],
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "source_agent": EXPERT_ROUTER_AGENT,
                "handoff_tool_name": HANDOFF_TOOL_NAME,
                "handoff_description": HANDOFF_DESCRIPTION,
                "handoff_input_schema": HANDOFF_INPUT_SCHEMA,
                "expert_router_instructions": EXPERT_ROUTER_INSTRUCTIONS,
                "target_instructions": SECONDARY_MARKET_ANALYST_INSTRUCTIONS,
                "prompt_preview": prompt[:240],
                "raw_model_preview": raw[:240],
            },
        )
        trace.metadata["expert_profile"] = EXPERT_PROFILE
        trace.metadata["expert_handoff"] = handoff
        errors = [parse_error] if parse_error else []
        return OperatorResult(
            logs=[f"{EXPERT_ROUTER_AGENT} invoked {HANDOFF_TOOL_NAME} -> {EXPERT_PROFILE}。"],
            errors=errors,
            metadata={
                "expert_handoff": handoff,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "operator_kind": "llm_operator",
                "operator_mode": "handoff_router",
                "llm_input": prompt,
                "llm_output": raw,
            },
        )


def build_expert_router_prompt(*, user_query: str, inferred: dict[str, Any]) -> str:
    """Build the model prompt that makes handoff routing instruction-driven."""

    return (
        f"{EXPERT_ROUTER_INSTRUCTIONS}\n\n"
        "Known local routing hints from the application:\n"
        f"{json.dumps(inferred, ensure_ascii=False, indent=2)}\n\n"
        "User message:\n"
        f"{user_query}\n"
    )


def build_secondary_market_handoff(
    *,
    user_query: str,
    inferred: dict[str, Any],
    packet: dict[str, Any],
    prompt: str,
    raw_model_output: str,
    parse_error: str | None = None,
) -> dict[str, Any]:
    """Normalize a router tool call into durable trace metadata."""

    selected_expert = str(packet.get("selected_expert") or EXPERT_PROFILE)
    tool_name = str(packet.get("tool_name") or HANDOFF_TOOL_NAME)
    route_warnings: list[str] = []
    if selected_expert != EXPERT_PROFILE:
        route_warnings.append(f"unsupported_selected_expert:{selected_expert}")
        selected_expert = EXPERT_PROFILE
    if tool_name != HANDOFF_TOOL_NAME:
        route_warnings.append(f"unsupported_handoff_tool:{tool_name}")
        tool_name = HANDOFF_TOOL_NAME
    if parse_error:
        route_warnings.append("router_output_parse_failed")

    missing_context = _string_list(packet.get("missing_context")) or list(inferred["missing_context"])
    reason = str(packet.get("reason") or "用户请求需要二级市场分析专家接管。")
    asset = str(packet.get("asset_or_market") or inferred["asset_or_market"])
    horizon = str(packet.get("time_horizon") or inferred["time_horizon"])
    user_intent = str(packet.get("user_intent") or "market_analysis")

    return {
        "handoff_kind": "agents_sdk_tool_handoff",
        "source_agent": EXPERT_ROUTER_AGENT,
        "target_agent": selected_expert,
        "selected_expert": selected_expert,
        "tool_name": tool_name,
        "tool_description": HANDOFF_DESCRIPTION,
        "handoff_description": HANDOFF_DESCRIPTION,
        "handoff_input_schema": HANDOFF_INPUT_SCHEMA,
        "handoff_reason": reason,
        "asset_or_market": asset,
        "time_horizon": horizon,
        "user_intent": user_intent,
        "missing_context": missing_context,
        "compliance_constraints": [
            "不得提供个性化投资建议",
            "必须区分事实、假设和推断",
            "必须给出风险和失效条件",
            "不得伪造实时市场数据",
        ],
        "router_instructions": EXPERT_ROUTER_INSTRUCTIONS,
        "target_instructions": SECONDARY_MARKET_ANALYST_INSTRUCTIONS,
        "handoff_input": {
            "reason": reason,
            "asset_or_market": asset,
            "time_horizon": horizon,
            "user_intent": user_intent,
            "missing_context": missing_context,
        },
        "handoff_output": f"Control transferred to {selected_expert}.",
        "original_user_query": user_query,
        "llm_input": prompt,
        "llm_output": raw_model_output,
        "route_warnings": route_warnings,
    }


def _infer_routing_context(user_query: str) -> dict[str, Any]:
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
    if required_fresh:
        missing.extend(["实时价格", "成交量", "资金流", "最新新闻"])
    return {
        "asset_or_market": asset,
        "market_type": _infer_market_type(user_query),
        "time_horizon": horizon,
        "geography": _infer_geography(user_query),
        "required_fresh_data": required_fresh,
        "missing_context": missing,
    }


def _parse_router_packet(raw: str) -> tuple[dict[str, Any], str | None]:
    text = raw.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}, "ExpertRouter did not return a JSON handoff tool call."
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            return {}, f"ExpertRouter handoff JSON parse failed: {exc}"
    if not isinstance(parsed, dict):
        return {}, "ExpertRouter handoff output was not a JSON object."
    return parsed, None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]

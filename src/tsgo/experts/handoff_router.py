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
HANDOFF_KIND = "agents_sdk_tool_handoff"
HANDOFF_TOOL_NAME = "transfer_to_secondary_market_analyst"
ROUTING_SOURCE_LLM_JSON = "llm_router_json"
ROUTING_SOURCE_LOCAL_FALLBACK = "local_inference_fallback"
VALID_TIME_HORIZONS = {
    "intraday",
    "short_term",
    "swing",
    "medium_term",
    "long_term",
    "unknown",
}
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
        handoff_logs = build_handoff_logs(handoff)

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
                "handoff_kind": HANDOFF_KIND,
                "handoff_tool_name": HANDOFF_TOOL_NAME,
                "handoff_description": HANDOFF_DESCRIPTION,
                "handoff_input_schema": HANDOFF_INPUT_SCHEMA,
                "handoff_input": handoff["handoff_input"],
                "handoff_output": handoff["handoff_output"],
                "handoff_status": handoff["handoff_status"],
                "routing_decision_source": handoff["routing_decision_source"],
                "routing_confidence": handoff["routing_confidence"],
                "route_warnings": handoff["route_warnings"],
                "handoff_log": handoff_logs,
                "expert_router_instructions": EXPERT_ROUTER_INSTRUCTIONS,
                "target_instructions": SECONDARY_MARKET_ANALYST_INSTRUCTIONS,
                "prompt_preview": prompt[:240],
                "raw_model_preview": raw[:240],
            },
        )
        trace.metadata["expert_profile"] = EXPERT_PROFILE
        trace.metadata["expert_handoff"] = handoff
        trace.metadata["handoff_log"] = handoff_logs

        errors = [parse_error] if parse_error else []
        return OperatorResult(
            logs=handoff_logs,
            errors=errors,
            metadata={
                "expert_handoff": handoff,
                "prompt_id": STAGE_PROMPT_IDS[self.name],
                "operator_kind": "llm_operator",
                "operator_mode": "handoff_router",
                "routing_decision_source": handoff["routing_decision_source"],
                "routing_confidence": handoff["routing_confidence"],
                "handoff_status": handoff["handoff_status"],
                "route_warnings": handoff["route_warnings"],
                "handoff_log": handoff_logs,
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

    route_warnings: list[str] = []
    if parse_error:
        route_warnings.append("router_output_parse_failed")

    selected_expert = _string_field(packet, "selected_expert", EXPERT_PROFILE, route_warnings)
    tool_name = _string_field(packet, "tool_name", HANDOFF_TOOL_NAME, route_warnings)
    if selected_expert != EXPERT_PROFILE:
        route_warnings.append(f"unsupported_selected_expert:{selected_expert}")
        selected_expert = EXPERT_PROFILE
    if tool_name != HANDOFF_TOOL_NAME:
        route_warnings.append(f"unsupported_handoff_tool:{tool_name}")
        tool_name = HANDOFF_TOOL_NAME

    reason = _string_field(packet, "reason", "用户请求需要二级市场分析专家接管。", route_warnings)
    asset = _string_field(packet, "asset_or_market", str(inferred["asset_or_market"]), route_warnings)
    horizon = _normalize_time_horizon(
        _string_field(packet, "time_horizon", str(inferred["time_horizon"]), route_warnings),
        route_warnings,
    )
    user_intent = _string_field(packet, "user_intent", "market_analysis", route_warnings)
    if user_intent != "market_analysis":
        route_warnings.append(f"unsupported_user_intent:{user_intent}")
        user_intent = "market_analysis"

    missing_context = _merge_missing_context(
        _string_list(packet.get("missing_context")),
        list(inferred["missing_context"]),
    )
    decision_source = ROUTING_SOURCE_LOCAL_FALLBACK if parse_error else ROUTING_SOURCE_LLM_JSON
    handoff_input = {
        "reason": reason,
        "asset_or_market": asset,
        "time_horizon": horizon,
        "user_intent": user_intent,
        "missing_context": missing_context,
    }

    return {
        "handoff_kind": HANDOFF_KIND,
        "handoff_status": "invoked",
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
        "handoff_input": handoff_input,
        "handoff_output": f"Control transferred to {selected_expert}.",
        "handoff_event_label": f"{EXPERT_ROUTER_AGENT} --{tool_name}--> {selected_expert}",
        "routing_decision_source": decision_source,
        "routing_confidence": "low" if route_warnings else "high",
        "original_user_query": user_query,
        "llm_input": prompt,
        "llm_output": raw_model_output,
        "prompt_preview": prompt[:240],
        "raw_model_preview": raw_model_output[:240],
        "route_warnings": route_warnings,
    }


def build_handoff_logs(handoff: dict[str, Any]) -> list[str]:
    """Return readable trace logs for router decision, tool call, and takeover."""

    missing_context = handoff.get("missing_context", [])
    missing_text = ", ".join(str(item) for item in missing_context) if missing_context else "none"
    warnings = handoff.get("route_warnings", [])
    logs = [
        f"{EXPERT_ROUTER_AGENT} loaded routing instructions.",
        (
            f"{EXPERT_ROUTER_AGENT} selected {handoff['selected_expert']} via "
            f"{handoff['tool_name']} because: {handoff['handoff_reason']}"
        ),
        (
            "handoff_input="
            f"asset_or_market={handoff['asset_or_market']}; "
            f"time_horizon={handoff['time_horizon']}; "
            f"user_intent={handoff['user_intent']}; "
            f"missing_context={missing_text}"
        ),
        f"{handoff['handoff_output']} Target instructions are now active.",
    ]
    if warnings:
        logs.append(f"handoff_warnings={', '.join(str(item) for item in warnings)}")
    return logs


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


def _string_field(packet: dict[str, Any], field: str, fallback: str, route_warnings: list[str]) -> str:
    value = packet.get(field)
    if value is None:
        route_warnings.append(f"missing_{field}")
        return fallback
    text = str(value).strip()
    if not text:
        route_warnings.append(f"empty_{field}")
        return fallback
    return text


def _normalize_time_horizon(value: str, route_warnings: list[str]) -> str:
    horizon = value.strip().lower()
    if horizon in VALID_TIME_HORIZONS:
        return horizon
    route_warnings.append(f"unsupported_time_horizon:{value}")
    return "unknown"


def _merge_missing_context(router_items: list[str], inferred_items: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*router_items, *inferred_items]:
        if item and item not in merged:
            merged.append(item)
    return merged


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]

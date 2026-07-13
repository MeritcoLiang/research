from __future__ import annotations

import json

from tsgo.experts.handoff_router import (
    EXPERT_ROUTER_AGENT,
    HANDOFF_KIND,
    HANDOFF_TOOL_NAME,
    ROUTING_SOURCE_LLM_JSON,
    ROUTING_SOURCE_LOCAL_FALLBACK,
    SecondaryMarketLLMExpertRouterOperator,
)
from tsgo.model_client import ScriptedModelClient
from tsgo.schema import ThoughtState, Trace


def test_llm_expert_router_uses_handoff_instructions() -> None:
    client = ScriptedModelClient(
        responses=[
            json.dumps(
                {
                    "tool_name": HANDOFF_TOOL_NAME,
                    "selected_expert": "SecondaryMarketAnalyst",
                    "reason": "用户请求需要二级市场分析专家接管。",
                    "asset_or_market": "AAPL",
                    "time_horizon": "medium_term",
                    "user_intent": "market_analysis",
                    "missing_context": ["实时价格", "成交量"],
                },
                ensure_ascii=False,
            )
        ]
    )
    trace = _trace_with_root("请分析 AAPL 的中期机会和风险。")

    result = SecondaryMarketLLMExpertRouterOperator(client).run(
        user_query=trace.user_query,
        states=trace.states,
        trace=trace,
    )

    handoff = trace.metadata["expert_handoff"]
    assert not result.errors
    assert client.prompts
    assert HANDOFF_TOOL_NAME in client.prompts[0]
    assert "Your job is routing, not answering" in client.prompts[0]
    assert handoff["handoff_kind"] == HANDOFF_KIND
    assert handoff["source_agent"] == EXPERT_ROUTER_AGENT
    assert handoff["tool_name"] == HANDOFF_TOOL_NAME
    assert handoff["selected_expert"] == "SecondaryMarketAnalyst"
    assert handoff["target_instructions"]
    assert handoff["routing_decision_source"] == ROUTING_SOURCE_LLM_JSON
    assert handoff["routing_confidence"] == "high"
    assert handoff["handoff_event_label"] == f"{EXPERT_ROUTER_AGENT} --{HANDOFF_TOOL_NAME}--> SecondaryMarketAnalyst"
    assert trace.task_info is not None
    assert trace.task_info.metadata["handoff_tool_name"] == HANDOFF_TOOL_NAME
    assert trace.task_info.metadata["expert_router_instructions"]
    assert trace.task_info.metadata["handoff_log"] == result.logs
    assert trace.metadata["handoff_log"] == result.logs
    assert any("selected SecondaryMarketAnalyst" in log for log in result.logs)
    assert any("handoff_input=asset_or_market=AAPL" in log for log in result.logs)


def test_llm_expert_router_records_parse_warning_without_losing_handoff() -> None:
    client = ScriptedModelClient(responses=["not json"])
    trace = _trace_with_root("请从二级市场角度分析美股。")

    result = SecondaryMarketLLMExpertRouterOperator(client).run(
        user_query=trace.user_query,
        states=trace.states,
        trace=trace,
    )

    handoff = trace.metadata["expert_handoff"]
    assert result.errors
    assert handoff["selected_expert"] == "SecondaryMarketAnalyst"
    assert handoff["routing_decision_source"] == ROUTING_SOURCE_LOCAL_FALLBACK
    assert handoff["routing_confidence"] == "low"
    assert "router_output_parse_failed" in handoff["route_warnings"]
    assert any("handoff_warnings=" in log for log in result.logs)


def test_llm_expert_router_normalizes_unsupported_tool_and_target() -> None:
    client = ScriptedModelClient(
        responses=[
            json.dumps(
                {
                    "tool_name": "transfer_to_generalist",
                    "selected_expert": "Generalist",
                    "reason": "router picked the wrong tool",
                    "asset_or_market": "BTC",
                    "time_horizon": "tomorrow",
                    "user_intent": "chat",
                    "missing_context": [],
                }
            )
        ]
    )
    trace = _trace_with_root("分析 BTC 现在的二级市场风险。")

    result = SecondaryMarketLLMExpertRouterOperator(client).run(
        user_query=trace.user_query,
        states=trace.states,
        trace=trace,
    )

    handoff = trace.metadata["expert_handoff"]
    assert not result.errors
    assert handoff["tool_name"] == HANDOFF_TOOL_NAME
    assert handoff["selected_expert"] == "SecondaryMarketAnalyst"
    assert handoff["time_horizon"] == "unknown"
    assert handoff["user_intent"] == "market_analysis"
    assert "unsupported_handoff_tool:transfer_to_generalist" in handoff["route_warnings"]
    assert "unsupported_selected_expert:Generalist" in handoff["route_warnings"]
    assert "unsupported_time_horizon:tomorrow" in handoff["route_warnings"]
    assert "unsupported_user_intent:chat" in handoff["route_warnings"]
    assert handoff["routing_confidence"] == "low"
    assert any("handoff_warnings=" in log for log in result.logs)


def _trace_with_root(user_query: str) -> Trace:
    trace = Trace(id="trace_test", user_query=user_query)
    root = ThoughtState(
        id="root_test",
        parent_ids=[],
        stage="root",
        user_query=trace.user_query,
        draft=trace.user_query,
        status="draft",
    )
    trace.add_state(root)
    return trace

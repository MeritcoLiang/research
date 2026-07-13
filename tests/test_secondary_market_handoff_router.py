from __future__ import annotations

import json

from tsgo.experts.handoff_router import HANDOFF_TOOL_NAME, SecondaryMarketLLMExpertRouterOperator
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
    trace = Trace(id="trace_test", user_query="请分析 AAPL 的中期机会和风险。")
    root = ThoughtState(
        id="root_test",
        parent_ids=[],
        stage="root",
        user_query=trace.user_query,
        draft=trace.user_query,
        status="draft",
    )
    trace.add_state(root)

    result = SecondaryMarketLLMExpertRouterOperator(client).run(
        user_query=trace.user_query,
        states=[root],
        trace=trace,
    )

    assert not result.errors
    assert client.prompts
    assert HANDOFF_TOOL_NAME in client.prompts[0]
    assert "Your job is routing, not answering" in client.prompts[0]
    assert trace.metadata["expert_handoff"]["handoff_kind"] == "agents_sdk_tool_handoff"
    assert trace.metadata["expert_handoff"]["source_agent"] == "ExpertRouter"
    assert trace.metadata["expert_handoff"]["tool_name"] == HANDOFF_TOOL_NAME
    assert trace.metadata["expert_handoff"]["selected_expert"] == "SecondaryMarketAnalyst"
    assert trace.metadata["expert_handoff"]["target_instructions"]
    assert trace.task_info is not None
    assert trace.task_info.metadata["handoff_tool_name"] == HANDOFF_TOOL_NAME
    assert trace.task_info.metadata["expert_router_instructions"]


def test_llm_expert_router_records_parse_warning_without_losing_handoff() -> None:
    client = ScriptedModelClient(responses=["not json"])
    trace = Trace(id="trace_test", user_query="请从二级市场角度分析美股。")
    root = ThoughtState(
        id="root_test",
        parent_ids=[],
        stage="root",
        user_query=trace.user_query,
        draft=trace.user_query,
        status="draft",
    )
    trace.add_state(root)

    result = SecondaryMarketLLMExpertRouterOperator(client).run(
        user_query=trace.user_query,
        states=[root],
        trace=trace,
    )

    assert result.errors
    assert trace.metadata["expert_handoff"]["selected_expert"] == "SecondaryMarketAnalyst"
    assert "router_output_parse_failed" in trace.metadata["expert_handoff"]["route_warnings"]

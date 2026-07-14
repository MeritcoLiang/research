from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from .instructions import AIDC_PROGRESS_EXPERT_INSTRUCTIONS
from .models import AIDCProgressReport, RunCreateRequest
from .provider import ProviderSettings, build_model
from .sources import get_registry

ProgressCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]


def build_prompt(payload: RunCreateRequest) -> str:
    request = payload.research
    registry = get_registry(request.state, request.county)
    seed_queries = registry.queries(request)
    query_preview = "\n".join(f"- {item}" for item in seed_queries[:30])
    return f"""
Research the following AIDC project and return AIDCProgressReport.

INPUT REQUEST
{request.model_dump_json(indent=2)}

JURISDICTION-SPECIFIC SOURCE MAP
{registry.render(request)}

DETERMINISTIC SEED QUERY EXAMPLES
These are examples, not an exhaustive list. Search every newly discovered alias and identifier.
{query_preview}

RUN ACCEPTANCE RULES
- Treat the supplied operator identity as a hypothesis until confirmed.
- Resolve site, address/parcel, applicant/owner LLC, case IDs, permit IDs, and utility project names first.
- Search planning/agenda, permits, environment, power, property/GIS, legal/community, and local news before deciding current_stage.
- Do not include events after {request.as_of_date}.
- Return the structured report only.
""".strip()


def build_agent(payload: RunCreateRequest) -> tuple[Any, ProviderSettings]:
    try:
        from agents import Agent, ModelSettings, WebSearchTool
    except ImportError as exc:
        raise RuntimeError("缺少 Agents SDK：pip install -e .") from exc

    settings = ProviderSettings.resolve(payload.runtime)
    model = build_model(settings)
    agent = Agent(
        name="AIDCProgressExpert",
        instructions=AIDC_PROGRESS_EXPERT_INSTRUCTIONS,
        model=model,
        model_settings=ModelSettings(tool_choice="required"),
        tools=[
            WebSearchTool(
                search_context_size=settings.search_context_size,
                external_web_access=True,
            )
        ],
        output_type=AIDCProgressReport,
    )
    return agent, settings


async def run_research(payload: RunCreateRequest, progress: ProgressCallback) -> AIDCProgressReport:
    try:
        from agents import Runner
    except ImportError as exc:
        raise RuntimeError("缺少 Agents SDK：pip install -e .") from exc

    await progress("preparing", "正在解析运行配置和项目身份线索。", {})
    agent, settings = build_agent(payload)
    prompt = build_prompt(payload)
    await progress(
        "researching",
        f"研究已启动：provider={settings.provider}，model={settings.model}。",
        {"provider": settings.provider, "model": settings.model, "max_turns": settings.max_turns},
    )

    result = Runner.run_streamed(agent, input=prompt, max_turns=settings.max_turns)
    async for event in result.stream_events():
        event_type = getattr(event, "type", "")
        if event_type == "agent_updated_stream_event":
            new_agent = getattr(getattr(event, "new_agent", None), "name", "AIDCProgressExpert")
            await progress("agent", f"当前 Agent：{new_agent}", {"agent": new_agent})
            continue
        if event_type != "run_item_stream_event":
            continue
        name = str(getattr(event, "name", "item"))
        message = _event_message(name)
        details = {"sdk_event": name}
        item = getattr(event, "item", None)
        item_type = getattr(item, "type", None)
        if item_type:
            details["item_type"] = str(item_type)
        await progress("agent_event", message, details)

    await progress("validating", "Agent 已完成检索，正在校验结构化报告。", {})
    report = _coerce_report(result.final_output)
    await progress(
        "report_ready",
        f"报告已生成：stage={report.current_stage.value}，confidence={report.confidence:.0%}。",
        {"stage": report.current_stage.value, "confidence": report.confidence},
    )
    return report


def _event_message(name: str) -> str:
    messages = {
        "tool_called": "Agent 正在调用 Web Search。",
        "tool_output": "Web Search 已返回一批结果。",
        "tool_search_called": "Agent 正在定位需要的检索工具。",
        "tool_search_output_created": "检索工具已经加载。",
        "reasoning_item_created": "Agent 正在分析证据、解决冲突并判断阶段。",
        "message_output_created": "Agent 正在整理结构化报告。",
        "handoff_requested": "Agent 请求转交任务。",
        "handoff_occured": "任务已转交给新的 Agent。",
    }
    return messages.get(name, f"Agents SDK 事件：{name}")


def _coerce_report(output: Any) -> AIDCProgressReport:
    if isinstance(output, AIDCProgressReport):
        return output
    if isinstance(output, dict):
        return AIDCProgressReport.model_validate(output)
    if isinstance(output, str):
        text = output.strip()
        try:
            return AIDCProgressReport.model_validate_json(text)
        except Exception:
            try:
                return AIDCProgressReport.model_validate(json.loads(text))
            except Exception as exc:
                raise RuntimeError("Agent 返回内容无法解析为 AIDCProgressReport。") from exc
    raise RuntimeError(f"Agent 返回了不支持的 final_output 类型：{type(output).__name__}")

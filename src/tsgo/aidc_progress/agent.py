"""Runnable OpenAI Agents SDK implementation of AIDCProgressExpert."""

from __future__ import annotations

import json
from typing import Any

from .instructions import AIDC_PROGRESS_EXPERT_INSTRUCTIONS
from .models import AIDCProgressReport, AIDCResearchRequest, quality_warnings
from .provider import ProviderSettings, build_agent_model
from .sources import get_source_registry


def build_research_prompt(request: AIDCResearchRequest) -> str:
    registry = get_source_registry(request.state, request.county)
    seed_queries = registry.build_search_queries(request)
    query_preview = "\n".join(f"- {query}" for query in seed_queries[:24])
    return f"""
Research the following AIDC project and return AIDCProgressReport.

INPUT REQUEST
{request.model_dump_json(indent=2)}

JURISDICTION-SPECIFIC SOURCE MAP
{registry.render_for_prompt(request)}

DETERMINISTIC SEED QUERY EXAMPLES
These are examples, not an exhaustive search list. Search every newly discovered alias and identifier.
{query_preview}

SPECIAL ACCEPTANCE RULES FOR THIS RUN
- Treat every supplied operator identity as a hypothesis until confirmed.
- First resolve the exact site, parcel/address, applicant/owner LLC, and case/permit identifiers.
- Search all required lifecycle workstreams before deciding current_stage: planning/agenda, permits, environment, power, property/GIS, and local-news.
- Use the request.as_of_date as the retrieval/cutoff date; do not include later events.
- Return the structured report only.
""".strip()


def build_aidc_progress_agent(
    request: AIDCResearchRequest,
    *,
    provider: str | None = None,
    model_name: str | None = None,
    max_turns: int | None = None,
) -> tuple[Any, ProviderSettings]:
    """Construct the expert and resolved runtime settings without running it."""

    try:
        from agents import Agent, ModelSettings, WebSearchTool
    except ImportError as exc:
        raise RuntimeError("AIDC Agent 需要安装：pip install -e '.[aidc]'") from exc

    settings = ProviderSettings.from_env(
        provider=provider,
        model_name=model_name,
        max_turns=max_turns,
    )
    model = build_agent_model(settings)
    web_search = WebSearchTool(
        search_context_size=settings.search_context_size,
        external_web_access=True,
    )
    agent = Agent(
        name="AIDCProgressExpert",
        instructions=AIDC_PROGRESS_EXPERT_INSTRUCTIONS,
        model=model,
        model_settings=ModelSettings(tool_choice="required"),
        tools=[web_search],
        output_type=AIDCProgressReport,
    )
    return agent, settings


def run_aidc_progress(
    request: AIDCResearchRequest,
    *,
    provider: str | None = None,
    model_name: str | None = None,
    max_turns: int | None = None,
) -> AIDCProgressReport:
    """Run the live web-research agent synchronously and validate its report."""

    try:
        from agents import Runner
    except ImportError as exc:
        raise RuntimeError("AIDC Agent 需要安装：pip install -e '.[aidc]'") from exc

    agent, settings = build_aidc_progress_agent(
        request,
        provider=provider,
        model_name=model_name,
        max_turns=max_turns,
    )
    result = Runner.run_sync(
        agent,
        build_research_prompt(request),
        max_turns=settings.max_turns,
    )
    report = _coerce_report(result.final_output)
    warnings = quality_warnings(report)
    if warnings:
        report.research_gaps.extend(warning for warning in warnings if warning not in report.research_gaps)
    return report


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

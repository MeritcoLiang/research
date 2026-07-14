"""Markdown and JSON serialization for AIDC progress reports."""

from __future__ import annotations

import re
from pathlib import Path

from .models import AIDCProgressReport, StatusSection, TimelineEvent


def render_report_markdown(report: AIDCProgressReport) -> str:
    latest = report.latest_verified_event
    lines = [
        f"# {report.identity.canonical_name} — AIDC 进展报告",
        "",
        f"- **地点**：{report.jurisdiction.county}, {report.jurisdiction.state}",
        f"- **截至日期**：{report.as_of_date}",
        f"- **当前阶段**：`{report.current_stage.value}`",
        f"- **总体置信度**：{report.confidence:.0%}",
        f"- **当前判断**：{report.current_status}",
    ]
    if latest:
        lines.extend([
            f"- **最近已核实事件**：{latest.event_date} — {latest.summary}",
        ])
    if report.next_expected_milestone:
        lines.append(f"- **下一预期里程碑**：{report.next_expected_milestone}")

    lines.extend(["", "## 项目身份与别名", ""])
    identity_rows = [
        ("别名", report.identity.aliases),
        ("运营商", report.identity.operators),
        ("申请人", report.identity.applicants),
        ("开发商", report.identity.developers),
        ("持地 LLC", report.identity.owner_llcs),
        ("地址", report.identity.addresses),
        ("Parcel/PIN", report.identity.parcel_ids),
        ("规划案件", report.identity.case_numbers),
        ("许可编号", report.identity.permit_numbers),
        ("电力项目", report.identity.utility_project_names),
    ]
    for label, values in identity_rows:
        lines.append(f"- **{label}**：{_join(values)}")
    for note in report.identity.identity_notes:
        lines.append(f"- **身份说明**：{note}")

    lines.extend(["", "## 分项状态", ""])
    sections = [
        ("规划与审批", report.approval_status),
        ("建设", report.construction_status),
        ("电力与输电", report.power_status),
        ("环境许可", report.environmental_status),
        ("水务、道路与基础设施", report.infrastructure_status),
        ("法律与社区风险", report.legal_and_community_status),
    ]
    for title, section in sections:
        lines.extend(_render_status(title, section))

    lines.extend(["", "## 时间线", ""])
    if report.timeline:
        lines.extend(_render_event(event) for event in report.timeline)
    else:
        lines.append("尚未找到可验证时间线。")

    lines.extend(["", "## 来源", ""])
    for index, source in enumerate(report.sources, start=1):
        dates = []
        if source.event_date:
            dates.append(f"事件 {source.event_date}")
        if source.publication_date:
            dates.append(f"发布 {source.publication_date}")
        dates.append(f"检索 {source.retrieved_date}")
        lines.append(
            f"{index}. **[{source.authority_grade}] {source.title}** — {source.publisher}；"
            f"{'；'.join(dates)}；置信度 {source.confidence:.0%}  "
        )
        lines.append(f"   {source.url}")
        lines.append(f"   - 证据说明：{source.evidence_note}")
        if source.supported_claims:
            lines.append(f"   - 支持结论：{_join(source.supported_claims)}")

    if report.source_conflicts:
        lines.extend(["", "## 来源冲突", ""])
        for conflict in report.source_conflicts:
            lines.append(f"- **{conflict.topic}**：{conflict.resolution}")
            for position in conflict.positions:
                lines.append(f"  - {position}")

    lines.extend(["", "## 未解决问题与研究缺口", ""])
    gaps = [*report.unresolved_questions, *report.research_gaps]
    if gaps:
        lines.extend(f"- {gap}" for gap in _dedupe(gaps))
    else:
        lines.append("- 无重大未解决问题。")
    return "\n".join(lines).rstrip() + "\n"


def save_report(report: AIDCProgressReport, output_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    slug = _slugify(report.identity.canonical_name or report.request.name)
    stem = f"{slug}-{report.as_of_date}"
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_report_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _render_status(title: str, section: StatusSection) -> list[str]:
    lines = [f"### {title}", "", f"**状态**：{section.status}（置信度 {section.confidence:.0%}）"]
    if section.verified_facts:
        lines.append("")
        lines.append("已核实：")
        lines.extend(f"- {fact}" for fact in section.verified_facts)
    if section.pending_items:
        lines.append("")
        lines.append("待确认：")
        lines.extend(f"- {item}" for item in section.pending_items)
    if section.source_urls:
        lines.append("")
        lines.append("来源：" + "；".join(str(url) for url in section.source_urls))
    lines.append("")
    return lines


def _render_event(event: TimelineEvent) -> str:
    inference = "（推断）" if event.is_inference else ""
    return (
        f"- **{event.event_date}** `{event.stage.value}` / {event.event_type} / {event.status}{inference}："
        f"{event.summary} — " + "；".join(str(url) for url in event.source_urls)
    )


def _join(values: list[str]) -> str:
    return "；".join(values) if values else "未确认"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "aidc-project"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))

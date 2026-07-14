from __future__ import annotations

from .models import AIDCProgressReport, StatusSection, TimelineEvent


def render_markdown(report: AIDCProgressReport) -> str:
    lines = [
        f"# {report.identity.canonical_name} — AIDC 进展报告",
        "",
        f"- **地点**：{report.jurisdiction.county}, {report.jurisdiction.state}",
        f"- **截至日期**：{report.as_of_date}",
        f"- **当前阶段**：`{report.current_stage.value}`",
        f"- **总体置信度**：{report.confidence:.0%}",
        f"- **当前判断**：{report.current_status}",
    ]
    if report.latest_verified_event:
        lines.append(
            f"- **最近已核实事件**：{report.latest_verified_event.event_date} — "
            f"{report.latest_verified_event.summary}"
        )
    if report.next_expected_milestone:
        lines.append(f"- **下一预期里程碑**：{report.next_expected_milestone}")

    lines.extend(["", "## 项目身份", ""])
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
    for title, section in [
        ("规划与审批", report.approval_status),
        ("建设", report.construction_status),
        ("电力与输电", report.power_status),
        ("环境许可", report.environmental_status),
        ("水务、道路与基础设施", report.infrastructure_status),
        ("法律与社区风险", report.legal_and_community_status),
    ]:
        lines.extend(_render_status(title, section))

    lines.extend(["", "## 时间线", ""])
    lines.extend(_render_event(event) for event in report.timeline)
    if not report.timeline:
        lines.append("尚未找到可验证时间线。")

    lines.extend(["", "## 来源", ""])
    for index, source in enumerate(report.sources, 1):
        lines.append(
            f"{index}. **[{source.authority_grade}] {source.title}** — {source.publisher}；"
            f"置信度 {source.confidence:.0%}"
        )
        lines.append(f"   - {source.url}")
        lines.append(f"   - 证据说明：{source.evidence_note}")

    if report.source_conflicts:
        lines.extend(["", "## 来源冲突", ""])
        for conflict in report.source_conflicts:
            lines.append(f"- **{conflict.topic}**：{conflict.resolution}")
            lines.extend(f"  - {position}" for position in conflict.positions)

    gaps = list(dict.fromkeys([*report.unresolved_questions, *report.research_gaps]))
    lines.extend(["", "## 未解决问题与研究缺口", ""])
    lines.extend(f"- {gap}" for gap in gaps)
    if not gaps:
        lines.append("- 无重大未解决问题。")
    return "\n".join(lines).rstrip() + "\n"


def _render_status(title: str, section: StatusSection) -> list[str]:
    lines = [f"### {title}", "", f"**状态**：{section.status}（置信度 {section.confidence:.0%}）"]
    if section.verified_facts:
        lines.extend(["", "已核实：", *[f"- {item}" for item in section.verified_facts]])
    if section.pending_items:
        lines.extend(["", "待确认：", *[f"- {item}" for item in section.pending_items]])
    if section.source_urls:
        lines.extend(["", "来源：" + "；".join(str(item) for item in section.source_urls)])
    lines.append("")
    return lines


def _render_event(event: TimelineEvent) -> str:
    inference = "（推断）" if event.is_inference else ""
    return (
        f"- **{event.event_date}** `{event.stage.value}` / {event.event_type} / "
        f"{event.status}{inference}：{event.summary} — "
        + "；".join(str(item) for item in event.source_urls)
    )


def _join(values: list[str]) -> str:
    return "；".join(values) if values else "未确认"

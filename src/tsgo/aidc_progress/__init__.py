"""AIDC project-progress research expert built with the OpenAI Agents SDK."""

from .agent import build_aidc_progress_agent, build_research_prompt, run_aidc_progress
from .instructions import AIDC_PROGRESS_EXPERT_INSTRUCTIONS
from .models import (
    AIDCProgressReport,
    AIDCResearchRequest,
    JurisdictionFinding,
    ProjectIdentity,
    ProjectStage,
    SourceConflict,
    SourceRecord,
    StatusSection,
    TimelineEvent,
    quality_warnings,
)
from .render import render_report_markdown, save_report
from .sources import JurisdictionSourceRegistry, SourceTarget, get_source_registry

__all__ = [
    "AIDCProgressReport",
    "AIDCResearchRequest",
    "AIDC_PROGRESS_EXPERT_INSTRUCTIONS",
    "JurisdictionFinding",
    "JurisdictionSourceRegistry",
    "ProjectIdentity",
    "ProjectStage",
    "SourceConflict",
    "SourceRecord",
    "SourceTarget",
    "StatusSection",
    "TimelineEvent",
    "build_aidc_progress_agent",
    "build_research_prompt",
    "get_source_registry",
    "quality_warnings",
    "render_report_markdown",
    "run_aidc_progress",
    "save_report",
]

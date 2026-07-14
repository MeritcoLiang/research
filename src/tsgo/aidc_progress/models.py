"""Structured contracts for AIDC project-progress research."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ProjectStage(StrEnum):
    """Normalized lifecycle stage for an AIDC project or campus."""

    UNKNOWN = "unknown"
    RUMOR_SITE_SELECTION = "rumor_or_site_selection"
    LAND_ACQUISITION = "land_acquisition"
    PLANNING_APPLICATION = "planning_application"
    LAND_USE_APPROVED = "land_use_approved"
    SITE_DEVELOPMENT = "site_development"
    VERTICAL_CONSTRUCTION = "vertical_construction"
    POWER_INFRASTRUCTURE = "power_infrastructure"
    COMMISSIONING = "commissioning"
    PARTIALLY_OPERATIONAL = "partially_operational"
    OPERATIONAL = "operational"
    EXPANSION = "expansion"
    STALLED_OR_CANCELLED = "stalled_or_cancelled"


class AIDCResearchRequest(BaseModel):
    """Input accepted by the AIDC progress expert."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, description="Known project, campus, operator, or code name.")
    county: str = Field(min_length=2, description="County or county-equivalent jurisdiction.")
    state: str = Field(min_length=2, description="US state name or abbreviation.")
    aliases: list[str] = Field(default_factory=list)
    location_hints: list[str] = Field(default_factory=list)
    as_of_date: str = Field(description="Research cutoff date in YYYY-MM-DD format.")
    lookback_years: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def normalize_strings(self) -> "AIDCResearchRequest":
        self.name = self.name.strip()
        self.county = self.county.strip()
        self.state = self.state.strip()
        self.aliases = _dedupe(self.aliases)
        self.location_hints = _dedupe(self.location_hints)
        return self


class ProjectIdentity(BaseModel):
    """Resolved names and identifiers used across government systems."""

    model_config = ConfigDict(extra="forbid")

    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    applicants: list[str] = Field(default_factory=list)
    developers: list[str] = Field(default_factory=list)
    owner_llcs: list[str] = Field(default_factory=list)
    engineering_firms: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    parcel_ids: list[str] = Field(default_factory=list)
    case_numbers: list[str] = Field(default_factory=list)
    permit_numbers: list[str] = Field(default_factory=list)
    utility_project_names: list[str] = Field(default_factory=list)
    identity_notes: list[str] = Field(default_factory=list)


class JurisdictionFinding(BaseModel):
    """Resolved government and utility jurisdiction."""

    model_config = ConfigDict(extra="forbid")

    state: str
    county: str
    incorporated_place: str | None = None
    land_use_authority: str | None = None
    building_authority: str | None = None
    environmental_authorities: list[str] = Field(default_factory=list)
    electric_utilities: list[str] = Field(default_factory=list)
    transmission_authorities: list[str] = Field(default_factory=list)
    water_and_sewer_authorities: list[str] = Field(default_factory=list)
    jurisdiction_notes: list[str] = Field(default_factory=list)


class SourceRecord(BaseModel):
    """One source used to support material claims in the report."""

    model_config = ConfigDict(extra="forbid")

    title: str
    publisher: str
    source_type: str
    authority_grade: Literal["A", "B", "C", "D", "E"]
    url: HttpUrl
    publication_date: str | None = None
    event_date: str | None = None
    retrieved_date: str
    identifiers: list[str] = Field(default_factory=list)
    supported_claims: list[str] = Field(default_factory=list)
    evidence_note: str
    is_primary_source: bool
    confidence: float = Field(ge=0.0, le=1.0)


class TimelineEvent(BaseModel):
    """A dated milestone normalized from one or more sources."""

    model_config = ConfigDict(extra="forbid")

    event_date: str
    event_type: str
    stage: ProjectStage
    status: str
    summary: str
    source_urls: list[HttpUrl] = Field(min_length=1)
    is_inference: bool = False
    inference_basis: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class StatusSection(BaseModel):
    """Evidence-backed status for one project workstream."""

    model_config = ConfigDict(extra="forbid")

    status: str
    verified_facts: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SourceConflict(BaseModel):
    """Material disagreement that could not be fully resolved."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    positions: list[str] = Field(min_length=2)
    source_urls: list[HttpUrl] = Field(min_length=2)
    resolution: str
    unresolved: bool


class AIDCProgressReport(BaseModel):
    """Final structured output returned by the OpenAI Agents SDK agent."""

    model_config = ConfigDict(extra="forbid")

    request: AIDCResearchRequest
    identity: ProjectIdentity
    jurisdiction: JurisdictionFinding
    current_stage: ProjectStage
    current_status: str
    latest_verified_event: TimelineEvent | None = None
    next_expected_milestone: str | None = None
    approval_status: StatusSection
    construction_status: StatusSection
    power_status: StatusSection
    environmental_status: StatusSection
    infrastructure_status: StatusSection
    legal_and_community_status: StatusSection
    timeline: list[TimelineEvent] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    source_conflicts: list[SourceConflict] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    research_gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    as_of_date: str

    @model_validator(mode="after")
    def enforce_report_consistency(self) -> "AIDCProgressReport":
        self.timeline.sort(key=lambda item: item.event_date)
        if self.latest_verified_event is None:
            verified = [event for event in self.timeline if not event.is_inference]
            if verified:
                self.latest_verified_event = verified[-1]
        return self


def quality_warnings(report: AIDCProgressReport) -> list[str]:
    """Return deterministic quality warnings after the model output validates."""

    warnings: list[str] = []
    if not report.sources:
        warnings.append("报告没有来源记录。")
    if report.sources and not any(source.is_primary_source for source in report.sources):
        warnings.append("报告没有政府、法院或公用事业等一手来源。")
    if not report.timeline:
        warnings.append("报告没有可验证的事件时间线。")
    if report.current_stage is not ProjectStage.UNKNOWN and report.latest_verified_event is None:
        warnings.append("已判断项目阶段，但缺少 latest_verified_event。")
    material_sections = [
        report.approval_status,
        report.construction_status,
        report.power_status,
        report.environmental_status,
    ]
    if any(section.confidence >= 0.6 and not section.source_urls for section in material_sections):
        warnings.append("高置信度状态缺少 source_urls。")
    return warnings


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output

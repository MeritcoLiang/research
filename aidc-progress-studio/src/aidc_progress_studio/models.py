from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStage(StrEnum):
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
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2)
    county: str = Field(min_length=2)
    state: str = Field(min_length=2)
    aliases: list[str] = Field(default_factory=list)
    location_hints: list[str] = Field(default_factory=list)
    as_of_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    lookback_years: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def normalize(self) -> "AIDCResearchRequest":
        self.name = self.name.strip()
        self.county = self.county.strip()
        self.state = self.state.strip()
        self.aliases = _dedupe(self.aliases)
        self.location_hints = _dedupe(self.location_hints)
        return self


class RuntimeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["azure", "openai"] = "azure"
    model: str | None = None
    search_context_size: Literal["low", "medium", "high"] = "high"
    max_turns: int = Field(default=30, ge=2, le=100)


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research: AIDCResearchRequest
    runtime: RuntimeOptions = Field(default_factory=RuntimeOptions)


class ProjectIdentity(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    status: str
    verified_facts: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SourceConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    positions: list[str] = Field(min_length=2)
    source_urls: list[HttpUrl] = Field(min_length=2)
    resolution: str
    unresolved: bool


class AIDCProgressReport(BaseModel):
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
    def normalize_report(self) -> "AIDCProgressReport":
        self.timeline.sort(key=lambda item: item.event_date)
        if self.latest_verified_event is None:
            verified = [item for item in self.timeline if not item.is_inference]
            if verified:
                self.latest_verified_event = verified[-1]
        return self


class ProgressEvent(BaseModel):
    sequence: int
    timestamp: str = Field(default_factory=utc_now)
    kind: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class StoredRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["queued", "running", "completed", "error"] = "queued"
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    request: RunCreateRequest
    events: list[ProgressEvent] = Field(default_factory=list)
    report: AIDCProgressReport | None = None
    error: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {"completed", "error"}


class RunListItem(BaseModel):
    run_id: str
    status: str
    created_at: str
    updated_at: str
    name: str
    county: str
    state: str
    provider: str
    stage: ProjectStage | None = None
    confidence: float | None = None
    error: str | None = None


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            output.append(value)
    return output

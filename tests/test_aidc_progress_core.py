from __future__ import annotations

import json
from pathlib import Path

from tsgo.aidc_progress.agent import build_research_prompt
from tsgo.aidc_progress.models import (
    AIDCProgressReport,
    AIDCResearchRequest,
    JurisdictionFinding,
    ProjectIdentity,
    ProjectStage,
    SourceRecord,
    StatusSection,
    TimelineEvent,
    quality_warnings,
)
from tsgo.aidc_progress.provider import normalize_azure_openai_base_url
from tsgo.aidc_progress.render import render_report_markdown, save_report
from tsgo.aidc_progress.sources import get_source_registry


FIXTURE = Path(__file__).parent / "fixtures" / "aidc_loudoun_stone_ridge_request.json"


def load_request() -> AIDCResearchRequest:
    return AIDCResearchRequest.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_loudoun_registry_covers_required_sources_and_alias_queries() -> None:
    request = load_request()
    registry = get_source_registry(request.state, request.county)
    categories = {target.category for target in registry.targets}
    assert {
        "planning_and_zoning",
        "building_and_grading_permits",
        "environmental_permits",
        "power_and_transmission",
        "wetlands_and_section_404",
        "property_and_gis",
        "local_news",
    } <= categories
    assert any(target.domain == "www.loudoun.gov" for target in registry.targets)
    assert any(target.domain == "www.deq.virginia.gov" for target in registry.targets)
    assert any(target.domain == "www.scc.virginia.gov" for target in registry.targets)
    queries = registry.build_search_queries(request)
    assert any("Reeds Farm Lane" in query for query in queries)
    assert any("AWS Stone Ridge" in query for query in queries)
    assert any("grading permit" in query for query in queries)


def test_prompt_requires_identity_resolution_and_full_lifecycle_search() -> None:
    prompt = build_research_prompt(load_request())
    for expected in [
        "AWS Stone Ridge",
        "Reeds Farm Lane",
        "parcel/address",
        "planning/agenda",
        "permits",
        "environment",
        "power",
        "local-news",
    ]:
        assert expected in prompt


def test_request_deduplicates_aliases_case_insensitively() -> None:
    request = AIDCResearchRequest(
        name="AWS Stone Ridge",
        county="Loudoun County",
        state="Virginia",
        aliases=["Reeds Farm Lane", "reeds farm lane", " Reeds Farm Lane "],
        location_hints=[],
        as_of_date="2026-07-14",
    )
    assert request.aliases == ["Reeds Farm Lane"]


def test_report_quality_and_rendering(tmp_path: Path) -> None:
    request = load_request()
    url = "https://www.loudoun.gov/example"
    event = TimelineEvent(
        event_date="2026-01-15",
        event_type="planning_action",
        stage=ProjectStage.PLANNING_APPLICATION,
        status="filed",
        summary="A planning application was filed for the identified parcel.",
        source_urls=[url],
        confidence=0.8,
    )
    section = StatusSection(
        status="planning application identified",
        verified_facts=["Planning filing identified."],
        source_urls=[url],
        confidence=0.8,
    )
    unknown = StatusSection(status="not verified", pending_items=["Further records needed."], confidence=0.2)
    report = AIDCProgressReport(
        request=request,
        identity=ProjectIdentity(canonical_name="AWS Stone Ridge", aliases=["Reeds Farm Lane"]),
        jurisdiction=JurisdictionFinding(state="Virginia", county="Loudoun County"),
        current_stage=ProjectStage.PLANNING_APPLICATION,
        current_status="A planning application is verified; construction is not yet verified.",
        approval_status=section,
        construction_status=unknown,
        power_status=unknown,
        environmental_status=unknown,
        infrastructure_status=unknown,
        legal_and_community_status=unknown,
        timeline=[event],
        sources=[
            SourceRecord(
                title="Planning record",
                publisher="Loudoun County",
                source_type="planning_case",
                authority_grade="A",
                url=url,
                event_date="2026-01-15",
                retrieved_date="2026-07-14",
                supported_claims=["Planning application filed."],
                evidence_note="Official county record.",
                is_primary_source=True,
                confidence=0.9,
            )
        ],
        confidence=0.78,
        as_of_date="2026-07-14",
    )
    assert report.latest_verified_event == event
    assert quality_warnings(report) == []
    markdown = render_report_markdown(report)
    assert "规划批准" not in markdown
    assert "construction is not yet verified" in markdown
    json_path, markdown_path = save_report(report, tmp_path)
    assert json_path.exists()
    assert markdown_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["current_stage"] == "planning_application"


def test_azure_endpoint_normalization() -> None:
    assert normalize_azure_openai_base_url("https://example.services.ai.azure.com") == (
        "https://example.services.ai.azure.com/openai/v1/"
    )
    assert normalize_azure_openai_base_url("https://example.openai.azure.com/openai/v1/") == (
        "https://example.openai.azure.com/openai/v1/"
    )

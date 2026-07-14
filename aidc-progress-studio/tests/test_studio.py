from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from aidc_progress_studio.api import create_app
from aidc_progress_studio.models import (
    AIDCProgressReport,
    AIDCResearchRequest,
    JurisdictionFinding,
    ProjectIdentity,
    ProjectStage,
    RunCreateRequest,
    RuntimeOptions,
    SourceRecord,
    StatusSection,
    TimelineEvent,
)
from aidc_progress_studio.provider import normalize_azure_base_url
from aidc_progress_studio.render import render_markdown
from aidc_progress_studio.store import RunStore


def sample_request() -> RunCreateRequest:
    return RunCreateRequest(
        research=AIDCResearchRequest(
            name="AWS Stone Ridge",
            county="Loudoun County",
            state="Virginia",
            aliases=["Reeds Farm Lane", "reeds farm lane"],
            location_hints=["Stone Ridge"],
            as_of_date="2026-07-14",
        ),
        runtime=RuntimeOptions(provider="azure", model="gpt-5.4"),
    )


def sample_report() -> AIDCProgressReport:
    request = sample_request().research
    url = "https://www.loudoun.gov/example"
    event = TimelineEvent(
        event_date="2026-01-15",
        event_type="planning_action",
        stage=ProjectStage.PLANNING_APPLICATION,
        status="filed",
        summary="A planning application was filed.",
        source_urls=[url],
        confidence=0.8,
    )
    verified = StatusSection(
        status="planning application identified",
        verified_facts=["Planning filing identified."],
        source_urls=[url],
        confidence=0.8,
    )
    unknown = StatusSection(status="not verified", pending_items=["Further records needed."], confidence=0.2)
    return AIDCProgressReport(
        request=request,
        identity=ProjectIdentity(canonical_name=request.name, aliases=request.aliases),
        jurisdiction=JurisdictionFinding(state=request.state, county=request.county),
        current_stage=ProjectStage.PLANNING_APPLICATION,
        current_status="Planning is verified; construction is not verified.",
        approval_status=verified,
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
                evidence_note="Official county record.",
                is_primary_source=True,
                confidence=0.9,
            )
        ],
        confidence=0.78,
        as_of_date="2026-07-14",
    )


def test_models_render_and_endpoint_normalization() -> None:
    request = sample_request()
    assert request.research.aliases == ["Reeds Farm Lane"]
    report = sample_report()
    assert report.latest_verified_event is not None
    markdown = render_markdown(report)
    assert "construction is not verified" in markdown
    assert "Planning record" in markdown
    assert normalize_azure_base_url("https://example.services.ai.azure.com") == (
        "https://example.services.ai.azure.com/openai/v1/"
    )


def test_store_persists_run_and_reports(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = RunStore(tmp_path)
        run = await store.create(sample_request())
        await store.set_status(run.run_id, "running")
        await store.append_event(run.run_id, "researching", "Searching", {})
        await store.complete(run.run_id, sample_report())
        loaded = await store.get(run.run_id)
        assert loaded is not None and loaded.status == "completed"
        assert store.report_path(run.run_id, "json").exists()
        assert store.report_path(run.run_id, "md").exists()
        reloaded = RunStore(tmp_path)
        persisted = await reloaded.get(run.run_id)
        assert persisted is not None and persisted.report is not None

    asyncio.run(scenario())


def test_api_run_lifecycle_and_static_ui(tmp_path: Path) -> None:
    async def fake_handler(payload, progress):
        await progress("researching", "Fake web search", {"provider": payload.runtime.provider})
        await asyncio.sleep(0.01)
        return sample_report()

    app = create_app(data_dir=tmp_path, run_handler=fake_handler)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        index = client.get("/")
        assert index.status_code == 200
        assert "AIDC Progress Studio" in index.text
        response = client.post("/api/runs", json=sample_request().model_dump(mode="json"))
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        run = None
        for _ in range(50):
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] in {"completed", "error"}:
                break
            time.sleep(0.02)
        assert run is not None and run["status"] == "completed"
        assert run["report"]["current_stage"] == "planning_application"
        assert client.get(f"/api/runs/{run_id}/report.json").status_code == 200
        assert client.get(f"/api/runs/{run_id}/report.md").status_code == 200


def test_project_is_standalone_and_ui_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "thought-state-graph-orchestration" not in pyproject
    assert "aidc_progress_studio" in pyproject
    script = (root / "src" / "aidc_progress_studio" / "static" / "app.js").read_text(encoding="utf-8")
    for token in ["/api/runs", "/ws/runs/", "renderTimeline", "renderSources", "download-json"]:
        assert token in script
    raw_ps = (root / "run.ps1").read_bytes()
    assert raw_ps.startswith(b"\xef\xbb\xbf")

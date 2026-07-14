from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from .models import ProgressEvent, RunCreateRequest, RunListItem, StoredRun, utc_now
from .render import render_markdown


class RunStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.runs_dir = data_dir / "runs"
        self.reports_dir = data_dir / "reports"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._runs: dict[str, StoredRun] = {}
        self._subscribers: dict[str, set[asyncio.Queue[ProgressEvent]]] = defaultdict(set)
        self._load_existing()

    def _load_existing(self) -> None:
        for path in sorted(self.runs_dir.glob("*.json")):
            try:
                run = StoredRun.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if run.status in {"queued", "running"}:
                run.status = "error"
                run.error = "服务重启时任务尚未完成。"
                run.updated_at = utc_now()
            self._runs[run.run_id] = run

    async def create(self, request: RunCreateRequest) -> StoredRun:
        async with self._lock:
            run_id = f"run_{uuid4().hex[:16]}"
            run = StoredRun(run_id=run_id, request=request)
            self._runs[run_id] = run
            self._persist(run)
            return run.model_copy(deep=True)

    async def get(self, run_id: str) -> StoredRun | None:
        async with self._lock:
            run = self._runs.get(run_id)
            return run.model_copy(deep=True) if run else None

    async def list(self) -> list[RunListItem]:
        async with self._lock:
            runs = sorted(self._runs.values(), key=lambda item: item.created_at, reverse=True)
            return [
                RunListItem(
                    run_id=run.run_id,
                    status=run.status,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                    name=run.request.research.name,
                    county=run.request.research.county,
                    state=run.request.research.state,
                    provider=run.request.runtime.provider,
                    stage=run.report.current_stage if run.report else None,
                    confidence=run.report.confidence if run.report else None,
                    error=run.error,
                )
                for run in runs
            ]

    async def set_status(self, run_id: str, status: str, error: str | None = None) -> StoredRun:
        async with self._lock:
            run = self._require(run_id)
            run.status = status  # type: ignore[assignment]
            run.error = error
            run.updated_at = utc_now()
            self._persist(run)
            return run.model_copy(deep=True)

    async def append_event(self, run_id: str, kind: str, message: str, details: dict) -> ProgressEvent:
        async with self._lock:
            run = self._require(run_id)
            event = ProgressEvent(
                sequence=len(run.events) + 1,
                kind=kind,
                message=message,
                details=details,
            )
            run.events.append(event)
            run.updated_at = utc_now()
            self._persist(run)
            subscribers = list(self._subscribers.get(run_id, set()))
        for queue in subscribers:
            queue.put_nowait(event)
        return event

    async def complete(self, run_id: str, report) -> StoredRun:
        async with self._lock:
            run = self._require(run_id)
            run.status = "completed"
            run.report = report
            run.error = None
            run.updated_at = utc_now()
            self._persist(run)
            (self.reports_dir / f"{run_id}.md").write_text(render_markdown(report), encoding="utf-8")
            (self.reports_dir / f"{run_id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
            return run.model_copy(deep=True)

    async def subscribe(self, run_id: str) -> asyncio.Queue[ProgressEvent]:
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        async with self._lock:
            self._require(run_id)
            self._subscribers[run_id].add(queue)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[ProgressEvent]) -> None:
        async with self._lock:
            self._subscribers.get(run_id, set()).discard(queue)

    def report_path(self, run_id: str, extension: str) -> Path:
        return self.reports_dir / f"{run_id}.{extension}"

    def _require(self, run_id: str) -> StoredRun:
        run = self._runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        return run

    def _persist(self, run: StoredRun) -> None:
        path = self.runs_dir / f"{run.run_id}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        temp.replace(path)

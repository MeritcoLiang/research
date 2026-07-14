from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .agent import run_research
from .models import AIDCProgressReport, RunCreateRequest, StoredRun
from .store import RunStore

RunHandler = Callable[[RunCreateRequest, Callable[[str, str, dict[str, Any]], Awaitable[None]]], Awaitable[AIDCProgressReport]]


class RunManager:
    def __init__(self, store: RunStore, handler: RunHandler = run_research) -> None:
        self.store = store
        self.handler = handler
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self, request: RunCreateRequest) -> StoredRun:
        run = await self.store.create(request)
        task = asyncio.create_task(self._execute(run.run_id, request), name=f"aidc-{run.run_id}")
        self._tasks[run.run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run.run_id, None))
        return run

    async def _execute(self, run_id: str, request: RunCreateRequest) -> None:
        await self.store.set_status(run_id, "running")
        await self.store.append_event(run_id, "started", "任务已进入运行队列。", {})

        async def progress(kind: str, message: str, details: dict[str, Any]) -> None:
            await self.store.append_event(run_id, kind, message, details)

        try:
            report = await self.handler(request, progress)
            await self.store.complete(run_id, report)
            await self.store.append_event(run_id, "completed", "研究任务已完成，报告已保存。", {})
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            await self.store.set_status(run_id, "error", message)
            await self.store.append_event(run_id, "error", message, {"exception": exc.__class__.__name__})

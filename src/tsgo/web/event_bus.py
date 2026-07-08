"""Event sinks used by the WebSocket backend."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..events import TraceEvent


@dataclass(slots=True)
class AsyncQueueEventSink:
    """Thread-safe bridge from PipelineController events to an asyncio.Queue."""

    queue: asyncio.Queue[TraceEvent]
    loop: asyncio.AbstractEventLoop

    def emit(self, event: TraceEvent) -> None:
        self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

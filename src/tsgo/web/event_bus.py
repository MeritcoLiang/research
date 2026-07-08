"""Event sinks used by the WebSocket backend."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..events import TraceEvent


@dataclass(slots=True)
class AsyncQueueEventSink:
    """Synchronous EventSink implementation backed by an asyncio.Queue."""

    queue: asyncio.Queue[TraceEvent]

    def emit(self, event: TraceEvent) -> None:
        self.queue.put_nowait(event)

"""Realtime event primitives for thought-state orchestration.

The Web UI and CLI tests observe the same pipeline runtime through this event
contract. Events expose orchestration state, not hidden model chain-of-thought.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


@dataclass(slots=True)
class TraceEvent:
    """One observable pipeline event."""

    event_id: str
    trace_id: str
    session_id: str | None
    event_type: str
    stage: str | None
    state_id: str | None
    parent_ids: list[str]
    payload: dict[str, Any]
    timestamp: str

    @classmethod
    def create(
        cls,
        *,
        trace_id: str,
        session_id: str | None,
        event_type: str,
        stage: str | None = None,
        state_id: str | None = None,
        parent_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> "TraceEvent":
        return cls(
            event_id=f"event_{uuid4().hex[:12]}",
            trace_id=trace_id,
            session_id=session_id,
            event_type=event_type,
            stage=stage,
            state_id=state_id,
            parent_ids=parent_ids or [],
            payload=payload or {},
            timestamp=datetime.now(UTC).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventSink(Protocol):
    """Minimal sink interface used by PipelineController."""

    def emit(self, event: TraceEvent) -> None:
        """Consume one event."""


@dataclass(slots=True)
class NoopEventSink:
    """Default sink for callers that do not need realtime events."""

    def emit(self, event: TraceEvent) -> None:
        return None


@dataclass(slots=True)
class InMemoryEventSink:
    """Test sink that stores emitted events in order."""

    events: list[TraceEvent] = field(default_factory=list)

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]

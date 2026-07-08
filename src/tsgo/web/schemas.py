"""Pydantic schemas for the Web UI API."""

from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - only hit when web extras are missing
    raise RuntimeError("Web UI requires optional dependency: pip install -e '.[web]'") from exc


class CreateSessionResponse(BaseModel):
    session_id: str


class UserMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    num_branches: int = Field(default=4, ge=1, le=16)


class TraceSummaryResponse(BaseModel):
    session_id: str
    trace_id: str
    final_state_id: str | None
    final_status: str | None
    state_count: int
    event_count: int
    final_draft_preview: str | None


class GraphResponse(BaseModel):
    trace_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

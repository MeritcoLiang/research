"""Session management and Web-message runtime adapter.

The Web UI currently runs the SecondaryMarketAnalyst stage flow so every user
message produces the documented sequence:
ExpertRouter -> 10 business stages -> ThoughtGraph / TraceEvent / GraphSnapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from ..events import EventSink
from ..graph import trace_to_graph
from ..runtime import run_secondary_market_stage_flow
from ..schema import Trace


@dataclass(slots=True)
class WebSession:
    session_id: str
    traces: dict[str, Trace] = field(default_factory=dict)


@dataclass(slots=True)
class SessionManager:
    trace_dir: Path = Path("traces/web")
    sessions: dict[str, WebSession] = field(default_factory=dict)

    def create_session(self) -> WebSession:
        session = WebSession(session_id=f"session_{uuid4().hex[:12]}")
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> WebSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"未知 session_id：{session_id}") from exc

    def handle_user_message(
        self,
        *,
        session_id: str,
        message: str,
        num_branches: int = 6,
        event_sink: EventSink | None = None,
    ) -> Trace:
        """Run a Web UI message through the documented Stage flow."""

        session = self.get_session(session_id)
        trace_path = self.trace_dir / f"{session_id}.jsonl"
        trace = run_secondary_market_stage_flow(
            message,
            trace_path=str(trace_path),
            num_branches=num_branches,
            event_sink=event_sink,
            session_id=session_id,
        )
        session.traces[trace.id] = trace
        return trace

    def graph_for_trace(self, *, session_id: str, trace_id: str) -> dict:
        session = self.get_session(session_id)
        trace = session.traces[trace_id]
        return trace_to_graph(trace).to_dict()

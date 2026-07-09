"""Session management and Web-message runtime adapter.

The Web UI can run the deterministic SecondaryMarketAnalyst Stage flow or run
the same Stage flow with real LLM Operators. LLM selection does not create a new
execution semantic; it only chooses how Operators are implemented for this run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from ..azure_openai_client import AzureOpenAIResponsesModelClient
from ..deepseek_client import DeepSeekOpenAIChatModelClient
from ..events import EventSink
from ..graph import trace_to_graph
from ..model_client import ModelClient
from ..runtime import run_secondary_market_llm_stage_flow, run_secondary_market_stage_flow
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
        llm_provider: str = "stage_flow",
        event_sink: EventSink | None = None,
    ) -> Trace:
        """Run a Web UI message through the selected Operator implementation."""

        session = self.get_session(session_id)
        provider = _normalize_llm_provider(llm_provider)
        trace_path = self.trace_dir / f"{session_id}_{provider}.jsonl"

        if provider == "stage_flow":
            trace = run_secondary_market_stage_flow(
                message,
                trace_path=str(trace_path),
                num_branches=num_branches,
                event_sink=event_sink,
                session_id=session_id,
            )
        else:
            client = _model_client_for_provider(provider)
            trace = run_secondary_market_llm_stage_flow(
                message,
                model_client=client,
                trace_path=str(trace_path),
                num_branches=num_branches,
                event_sink=event_sink,
                session_id=session_id,
            )

        trace.metadata["web_llm_provider"] = provider
        session.traces[trace.id] = trace
        return trace

    def graph_for_trace(self, *, session_id: str, trace_id: str) -> dict:
        session = self.get_session(session_id)
        trace = session.traces[trace_id]
        return trace_to_graph(trace).to_dict()


def _normalize_llm_provider(provider: str) -> str:
    normalized = str(provider or "stage_flow").strip().lower()
    aliases = {
        "none": "stage_flow",
        "deterministic": "stage_flow",
        "secondary_market": "stage_flow",
        "secondary_market_stage_flow": "stage_flow",
        "azure": "azure_openai",
        "azure-openai": "azure_openai",
        "azure_openai": "azure_openai",
        "deepseek": "deepseek",
    }
    if normalized not in aliases:
        raise ValueError(f"不支持的 llm_provider：{provider}")
    return aliases[normalized]


def _model_client_for_provider(provider: str) -> ModelClient:
    if provider == "azure_openai":
        return AzureOpenAIResponsesModelClient.from_env()
    if provider == "deepseek":
        return DeepSeekOpenAIChatModelClient.from_env()
    raise ValueError(f"provider 不需要 ModelClient 或不受支持：{provider}")

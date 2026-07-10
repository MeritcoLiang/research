"""Session management and Web-message runtime adapter.

The Web UI can run the deterministic SecondaryMarketAnalyst Stage flow or run
the same Stage flow with real LLM Operators. LLM selection does not create a new
execution semantic; it only chooses how Operators are implemented for this run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from ..azure_openai_client import AzureOpenAIResponsesModelClient
from ..deepseek_client import DeepSeekOpenAIChatModelClient
from ..events import EventSink
from ..graph import trace_to_graph
from ..model_client import ModelClient
from ..runtime import run_secondary_market_llm_stage_flow, run_secondary_market_stage_flow
from ..schema import (
    Claim,
    ContextPacket,
    Evidence,
    Rubric,
    RubricItem,
    Score,
    Subtask,
    TaskInfo,
    ThoughtState,
    ToolOutput,
    Trace,
)


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

    def list_history(self) -> list[dict]:
        """List latest trace from each JSONL history file in trace_dir."""

        self.trace_dir.mkdir(parents=True, exist_ok=True)
        items: list[dict] = []
        for path in sorted(self.trace_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                trace_dict = _read_latest_trace_dict(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            items.append(_history_summary(path, trace_dict))
        return items

    def history_graph(self, history_id: str) -> dict:
        """Load a historical trace file and return its summary plus GraphSnapshot."""

        path = _safe_history_path(self.trace_dir, history_id)
        trace_dict = _read_latest_trace_dict(path)
        trace = _trace_from_dict(trace_dict)
        return {
            "summary": _history_summary(path, trace_dict),
            "graph": trace_to_graph(trace).to_dict(),
        }


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


def _safe_history_path(trace_dir: Path, history_id: str) -> Path:
    if not history_id or "/" in history_id or "\\" in history_id or history_id.startswith("."):
        raise KeyError(f"非法 history_id：{history_id}")
    path = trace_dir / history_id
    if path.suffix != ".jsonl" or not path.exists():
        raise KeyError(f"未知 history_id：{history_id}")
    return path


def _read_latest_trace_dict(path: Path) -> dict:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"history file is empty: {path}")
    return json.loads(lines[-1])


def _history_summary(path: Path, trace_dict: dict) -> dict:
    session_id, provider = _parse_history_filename(path)
    final_state_id = trace_dict.get("final_state_id")
    final_state = next((state for state in trace_dict.get("states", []) if state.get("id") == final_state_id), None)
    metadata = trace_dict.get("metadata", {}) if isinstance(trace_dict.get("metadata"), dict) else {}
    provider = str(metadata.get("web_llm_provider") or provider or metadata.get("runner") or "unknown")
    return {
        "history_id": path.name,
        "session_id": session_id,
        "llm_provider": provider,
        "trace_id": trace_dict.get("id", ""),
        "final_state_id": final_state_id,
        "final_status": final_state.get("status") if isinstance(final_state, dict) else None,
        "state_count": len(trace_dict.get("states", [])),
        "event_count": len(metadata.get("events", [])),
        "user_query_preview": str(trace_dict.get("user_query", ""))[:120],
        "final_draft_preview": str(final_state.get("draft", ""))[:600] if isinstance(final_state, dict) else None,
        "modified_time": path.stat().st_mtime,
    }


def _parse_history_filename(path: Path) -> tuple[str | None, str | None]:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 3 and parts[0] == "session":
        return "_".join(parts[:2]), "_".join(parts[2:])
    return None, None


def _trace_from_dict(raw: dict) -> Trace:
    return Trace(
        id=str(raw.get("id", "trace_unknown")),
        user_query=str(raw.get("user_query", "")),
        states=[_state_from_dict(item) for item in raw.get("states", []) if isinstance(item, dict)],
        task_info=_task_info_from_dict(raw.get("task_info")),
        context=_context_from_dict(raw.get("context")),
        rubric=_rubric_from_dict(raw.get("rubric")),
        subtasks=[_subtask_from_dict(item) for item in raw.get("subtasks", []) if isinstance(item, dict)],
        final_state_id=raw.get("final_state_id"),
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _state_from_dict(raw: dict) -> ThoughtState:
    return ThoughtState(
        id=str(raw.get("id", "state_unknown")),
        parent_ids=[str(item) for item in raw.get("parent_ids", [])],
        stage=str(raw.get("stage", "root")),
        user_query=str(raw.get("user_query", "")),
        task_type=str(raw.get("task_type", "unknown")),
        draft=raw.get("draft"),
        summary=raw.get("summary"),
        claims=[_claim_from_dict(item) for item in raw.get("claims", []) if isinstance(item, dict)],
        assumptions=[str(item) for item in raw.get("assumptions", [])],
        missing_info=[str(item) for item in raw.get("missing_info", [])],
        evidence=[_evidence_from_dict(item) for item in raw.get("evidence", []) if isinstance(item, dict)],
        tool_outputs=[_tool_output_from_dict(item) for item in raw.get("tool_outputs", []) if isinstance(item, dict)],
        critique=[str(item) for item in raw.get("critique", [])],
        score=_score_from_dict(raw.get("score")),
        uncertainty=[str(item) for item in raw.get("uncertainty", [])],
        failure_modes=[str(item) for item in raw.get("failure_modes", [])],
        status=str(raw.get("status", "draft")),
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _task_info_from_dict(raw: object) -> TaskInfo | None:
    if not isinstance(raw, dict):
        return None
    return TaskInfo(
        user_query=str(raw.get("user_query", "")),
        task_type=str(raw.get("task_type", "unknown")),
        difficulty=str(raw.get("difficulty", "medium")),
        requires_tools=bool(raw.get("requires_tools", False)),
        requires_citations=bool(raw.get("requires_citations", False)),
        requires_computation=bool(raw.get("requires_computation", False)),
        requires_user_context=bool(raw.get("requires_user_context", False)),
        answer_format=str(raw.get("answer_format", "structured_text")),
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _context_from_dict(raw: object) -> ContextPacket | None:
    if not isinstance(raw, dict):
        return None
    return ContextPacket(
        user_intent=str(raw.get("user_intent", "")),
        hard_constraints=[str(item) for item in raw.get("hard_constraints", [])],
        soft_preferences=[str(item) for item in raw.get("soft_preferences", [])],
        available_context=[str(item) for item in raw.get("available_context", [])],
        missing_context=[str(item) for item in raw.get("missing_context", [])],
        retrieved_evidence=[_evidence_from_dict(item) for item in raw.get("retrieved_evidence", []) if isinstance(item, dict)],
        tool_plan=[item for item in raw.get("tool_plan", []) if isinstance(item, dict)],
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _rubric_from_dict(raw: object) -> Rubric | None:
    if not isinstance(raw, dict):
        return None
    return Rubric(
        items=[_rubric_item_from_dict(item) for item in raw.get("items", []) if isinstance(item, dict)],
        hard_constraints=[str(item) for item in raw.get("hard_constraints", [])],
        soft_preferences=[str(item) for item in raw.get("soft_preferences", [])],
    )


def _rubric_item_from_dict(raw: dict) -> RubricItem:
    return RubricItem(
        name=str(raw.get("name", "")),
        weight=float(raw.get("weight", 0.0)),
        description=str(raw.get("description", "")),
        pass_threshold=raw.get("pass_threshold"),
    )


def _subtask_from_dict(raw: dict) -> Subtask:
    return Subtask(
        id=str(raw.get("id", "subtask")),
        question=str(raw.get("question", "")),
        task_type=str(raw.get("task_type", "unknown")),
        required_outputs=[str(item) for item in raw.get("required_outputs", [])],
        dependencies=[str(item) for item in raw.get("dependencies", [])],
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _claim_from_dict(raw: dict) -> Claim:
    return Claim(
        text=str(raw.get("text", "")),
        claim_type=str(raw.get("claim_type", "unknown")),
        confidence=raw.get("confidence"),
        evidence_ids=[str(item) for item in raw.get("evidence_ids", [])],
        verifier_notes=[str(item) for item in raw.get("verifier_notes", [])],
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _score_from_dict(raw: object) -> Score | None:
    if not isinstance(raw, dict):
        return None
    return Score(
        correctness=float(raw.get("correctness", 0.0)),
        completeness=float(raw.get("completeness", 0.0)),
        relevance=float(raw.get("relevance", 0.0)),
        clarity=float(raw.get("clarity", 0.0)),
        groundedness=float(raw.get("groundedness", 0.0)),
        safety=float(raw.get("safety", 1.0)),
        novelty=float(raw.get("novelty", 0.0)),
        actionability=float(raw.get("actionability", 0.0)),
        overall=float(raw.get("overall", 0.0)),
        notes=[str(item) for item in raw.get("notes", [])],
    )


def _evidence_from_dict(raw: dict) -> Evidence:
    return Evidence(
        id=str(raw.get("id", "evidence")),
        kind=str(raw.get("kind", "unknown")),
        content=str(raw.get("content", "")),
        source=raw.get("source"),
        reliability=raw.get("reliability"),
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )


def _tool_output_from_dict(raw: dict) -> ToolOutput:
    return ToolOutput(
        id=str(raw.get("id", "tool_output")),
        tool_name=str(raw.get("tool_name", "unknown")),
        input=raw.get("input", {}) if isinstance(raw.get("input"), dict) else {},
        output=raw.get("output"),
        success=bool(raw.get("success", False)),
        error=raw.get("error"),
        metadata=raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {},
    )

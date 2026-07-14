"""FastAPI backend for the Thought-State Graph Orchestration Web UI."""

from __future__ import annotations

import asyncio
import time

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Web UI requires optional dependency: pip install -e '.[web]'") from exc

from ..graph import event_to_graph_delta, trace_to_graph
from ..schema import Trace
from .event_bus import AsyncQueueEventSink
from .schemas import (
    CreateSessionResponse,
    GraphResponse,
    HistoryGraphResponse,
    HistoryListResponse,
    TraceSummaryResponse,
    UserMessageRequest,
)
from .sessions import SessionManager


app = FastAPI(title="Thought-State Graph Orchestration UI", version="0.3.0")
manager = SessionManager()
HEARTBEAT_INTERVAL_SECONDS = 5.0


@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    session = manager.create_session()
    return CreateSessionResponse(session_id=session.session_id)


@app.post("/api/sessions/{session_id}/messages", response_model=TraceSummaryResponse)
def post_message(session_id: str, request: UserMessageRequest) -> TraceSummaryResponse:
    try:
        trace = manager.handle_user_message(
            session_id=session_id,
            message=request.message,
            num_branches=request.num_branches,
            llm_provider=request.llm_provider,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _trace_summary(session_id, trace)


@app.get("/api/sessions/{session_id}/traces/{trace_id}/graph", response_model=GraphResponse)
def get_trace_graph(session_id: str, trace_id: str) -> GraphResponse:
    try:
        graph = manager.graph_for_trace(session_id=session_id, trace_id=trace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GraphResponse(**graph)


@app.get("/api/history", response_model=HistoryListResponse)
def list_history() -> HistoryListResponse:
    return HistoryListResponse(items=manager.list_history())


@app.get("/api/history/{history_id}", response_model=HistoryGraphResponse)
def load_history_graph(history_id: str) -> HistoryGraphResponse:
    try:
        payload = manager.history_graph(history_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HistoryGraphResponse(summary=payload["summary"], graph=GraphResponse(**payload["graph"]))


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        manager.ensure_session(session_id)
    except KeyError:
        await websocket.send_json({"type": "error", "message": f"非法 session_id：{session_id}"})
        await websocket.close(code=1008)
        return

    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "user_message":
                await websocket.send_json({"type": "error", "message": "只支持 type=user_message。"})
                continue

            content = str(message.get("content", "")).strip()
            if not content:
                await websocket.send_json({"type": "error", "message": "message 不能为空。"})
                continue

            num_branches = int(message.get("num_branches", 6))
            llm_provider = str(message.get("llm_provider", "stage_flow"))
            await websocket.send_json(
                {
                    "type": "run_started",
                    "llm_provider": llm_provider,
                    "num_branches": num_branches,
                }
            )

            queue: asyncio.Queue = asyncio.Queue()
            sink = AsyncQueueEventSink(queue=queue, loop=asyncio.get_running_loop())
            task = asyncio.create_task(
                asyncio.to_thread(
                    manager.handle_user_message,
                    session_id=session_id,
                    message=content,
                    num_branches=num_branches,
                    llm_provider=llm_provider,
                    event_sink=sink,
                )
            )

            active_stage = "starting"
            active_event_type = "run_started"
            last_activity = time.monotonic()
            while True:
                if task.done() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    if now - last_activity >= HEARTBEAT_INTERVAL_SECONDS:
                        await websocket.send_json(
                            {
                                "type": "run_heartbeat",
                                "stage": active_stage,
                                "last_event_type": active_event_type,
                                "waiting_seconds": round(now - last_activity, 1),
                                "message": f"仍在执行 {active_stage}，等待 Operator / LLM 返回。",
                            }
                        )
                        last_activity = now
                    continue

                active_stage = str(event.stage or active_stage)
                active_event_type = event.event_type
                last_activity = time.monotonic()
                await websocket.send_json({"type": "trace_event", "event": event.to_dict()})
                delta = event_to_graph_delta(event)
                if delta.get("type") != "event":
                    await websocket.send_json(delta)

            try:
                trace = task.result()
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(exc),
                        "stage": active_stage,
                        "last_event_type": active_event_type,
                    }
                )
                continue

            graph = trace_to_graph(trace).to_dict()
            await websocket.send_json(
                {
                    "type": "pipeline_completed",
                    "summary": _summary_to_dict(_trace_summary(session_id, trace)),
                    "graph": graph,
                }
            )
    except WebSocketDisconnect:
        return


def _trace_summary(session_id: str, trace: Trace) -> TraceSummaryResponse:
    final_state = next((state for state in trace.states if state.id == trace.final_state_id), None)
    return TraceSummaryResponse(
        session_id=session_id,
        trace_id=trace.id,
        final_state_id=trace.final_state_id,
        final_status=final_state.status if final_state else None,
        state_count=len(trace.states),
        event_count=len(trace.metadata.get("events", [])),
        final_draft_preview=(final_state.draft or "")[:600] if final_state else None,
    )


def _summary_to_dict(summary: TraceSummaryResponse) -> dict:
    if hasattr(summary, "model_dump"):
        return summary.model_dump()
    return summary.dict()

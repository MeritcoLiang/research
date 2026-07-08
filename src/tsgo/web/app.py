"""FastAPI backend for the Pipeline v0.2 Web UI.

The Web UI is an adapter over the shared runtime. Sending a message through the
WebSocket or HTTP endpoint is equivalent to running:

    python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
"""

from __future__ import annotations

import asyncio

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
except ImportError as exc:  # pragma: no cover - only hit when web extras are missing
    raise RuntimeError("Web UI requires optional dependency: pip install -e '.[web]'") from exc

from ..graph import event_to_graph_delta, trace_to_graph
from ..schema import Trace
from .event_bus import AsyncQueueEventSink
from .schemas import CreateSessionResponse, GraphResponse, TraceSummaryResponse, UserMessageRequest
from .sessions import SessionManager


app = FastAPI(title="Thought-State Graph Orchestration UI", version="0.2.0")
manager = SessionManager()


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
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _trace_summary(session_id, trace)


@app.get("/api/sessions/{session_id}/traces/{trace_id}/graph", response_model=GraphResponse)
def get_trace_graph(session_id: str, trace_id: str) -> GraphResponse:
    try:
        graph = manager.graph_for_trace(session_id=session_id, trace_id=trace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GraphResponse(**graph)


@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        manager.get_session(session_id)
    except KeyError:
        await websocket.send_json({"type": "error", "message": f"未知 session_id：{session_id}"})
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

            num_branches = int(message.get("num_branches", 4))
            queue: asyncio.Queue = asyncio.Queue()
            sink = AsyncQueueEventSink(queue=queue, loop=asyncio.get_running_loop())

            task = asyncio.create_task(
                asyncio.to_thread(
                    manager.handle_user_message,
                    session_id=session_id,
                    message=content,
                    num_branches=num_branches,
                    event_sink=sink,
                )
            )

            while True:
                if task.done() and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                await websocket.send_json({"type": "trace_event", "event": event.to_dict()})
                await websocket.send_json(event_to_graph_delta(event))

            trace = task.result()
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

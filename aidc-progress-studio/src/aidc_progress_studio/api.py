from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import RunCreateRequest
from .provider import load_environment
from .service import RunHandler, RunManager
from .store import RunStore

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"


def create_app(*, data_dir: Path | None = None, run_handler: RunHandler | None = None) -> FastAPI:
    load_environment()
    resolved_data_dir = data_dir or Path(os.getenv("AIDC_DATA_DIR", "data")).expanduser().resolve()
    store = RunStore(resolved_data_dir)
    manager = RunManager(store, run_handler) if run_handler else RunManager(store)

    app = FastAPI(title="AIDC Progress Studio", version="0.1.0")
    app.state.store = store
    app.state.manager = manager
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "service": "aidc-progress-studio"}

    @app.get("/api/config")
    async def config() -> dict:
        provider = os.getenv("AIDC_PROVIDER", "azure").strip().casefold() or "azure"
        return {
            "provider": provider if provider in {"azure", "openai"} else "azure",
            "azure_model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip(),
            "openai_model": os.getenv("AIDC_OPENAI_MODEL", "gpt-5.4").strip(),
            "search_context_size": os.getenv("AIDC_SEARCH_CONTEXT_SIZE", "high").strip(),
            "max_turns": int(os.getenv("AIDC_MAX_TURNS", "30")),
        }

    @app.post("/api/runs", status_code=202)
    async def create_run(payload: RunCreateRequest) -> dict:
        run = await manager.start(payload)
        return {"run_id": run.run_id, "status": run.status}

    @app.get("/api/runs")
    async def list_runs() -> dict:
        return {"items": [item.model_dump(mode="json") for item in await store.list()]}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run = await store.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="未知 run_id")
        return run.model_dump(mode="json")

    @app.get("/api/runs/{run_id}/report.md")
    async def get_markdown(run_id: str) -> FileResponse:
        path = store.report_path(run_id, "md")
        if not path.exists():
            raise HTTPException(status_code=404, detail="报告尚未生成")
        return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=f"{run_id}.md")

    @app.get("/api/runs/{run_id}/report.json")
    async def get_json_report(run_id: str) -> FileResponse:
        path = store.report_path(run_id, "json")
        if not path.exists():
            raise HTTPException(status_code=404, detail="报告尚未生成")
        return FileResponse(path, media_type="application/json", filename=f"{run_id}.json")

    @app.websocket("/ws/runs/{run_id}")
    async def run_stream(websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        run = await store.get(run_id)
        if not run:
            await websocket.send_json({"type": "error", "message": "未知 run_id"})
            await websocket.close(code=4404)
            return

        await websocket.send_json({"type": "snapshot", "run": run.model_dump(mode="json")})
        if run.terminal:
            await websocket.close()
            return

        queue = await store.subscribe(run_id)
        current_after_subscribe = await store.get(run_id)
        if current_after_subscribe and current_after_subscribe.terminal:
            await websocket.send_json({"type": "snapshot", "run": current_after_subscribe.model_dump(mode="json")})
            await store.unsubscribe(run_id, queue)
            await websocket.close()
            return
        try:
            while True:
                event = await queue.get()
                current = await store.get(run_id)
                await websocket.send_json(
                    {
                        "type": "event",
                        "event": event.model_dump(mode="json"),
                        "run": current.model_dump(mode="json") if current else None,
                    }
                )
                if current and current.terminal:
                    await websocket.close()
                    return
        except WebSocketDisconnect:
            return
        finally:
            await store.unsubscribe(run_id, queue)

    return app


app = create_app()

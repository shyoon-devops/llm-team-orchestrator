"""★ PoC 전용 — FastAPI application factory."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.events.bus import EventBus
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig, PipelineStatus, TaskStatus
from orchestrator.poc.mock_adapters import MockCLIAdapter
from orchestrator.web.routes import create_router
from orchestrator.web.ws import WebSocketManager


class AppState:
    """Shared application state."""

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.ws_manager = WebSocketManager(self.event_bus)
        self.artifact_store = ArtifactStore(tempfile.mkdtemp(prefix="orch-"))
        self.pipelines: dict[str, PipelineStatus] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    async def run_pipeline(self, task_id: str, task: str) -> None:
        """Run a pipeline in background."""
        config = AdapterConfig(api_key="mock", timeout=30)
        adapter = MockCLIAdapter(
            config=config,
            responses={"default": f"Mock response for: {task[:80]}"},
            latency_ms=200,
        )

        self.pipelines[task_id] = PipelineStatus(
            task_id=task_id, task=task, status=TaskStatus.RUNNING
        )

        graph = build_graph(adapter, adapter, adapter, self.artifact_store, self.event_bus)

        result = await graph.ainvoke(
            {
                "task": task,
                "plan_summary": "",
                "plan_artifact": "",
                "code_artifact": "",
                "review_summary": "",
                "review_artifact": "",
                "status": "",
                "error": "",
                "retry_count": 0,
                "messages": [],
            }
        )

        status = self.pipelines[task_id]
        status.status = (
            TaskStatus.COMPLETED if result["status"] == "reviewed" else TaskStatus.FAILED
        )
        status.error = result.get("error", "")
        status.artifacts = self.artifact_store.list_artifacts()
        status.messages = result.get("messages", [])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="LLM Team Orchestrator",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state = AppState()
    app.state.app_state = state

    router = create_router(state)
    app.include_router(router)

    @app.websocket("/ws/events")
    async def websocket_events(ws: WebSocket) -> None:
        await state.ws_manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            state.ws_manager.disconnect(ws)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)

"""★ PoC 전용 — FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.adapters.factory import AdapterFactory
from orchestrator.config.loader import load_config_with_defaults
from orchestrator.config.schema import AgentDef, OrchestratorConfig
from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.events.bus import EventBus
from orchestrator.events.tracker import AgentTracker
from orchestrator.events.types import EventType, OrchestratorEvent
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import PipelineStatus, TaskStatus
from orchestrator.web.routes import create_router
from orchestrator.web.ws import WebSocketManager

# Default agents when no config file exists
_DEFAULT_AGENTS: dict[str, AgentDef] = {
    "planner": AgentDef(cli="claude", role="architect", timeout=120),
    "implementer": AgentDef(cli="codex", role="engineer", timeout=300),
    "reviewer": AgentDef(cli="gemini", role="reviewer", timeout=120),
}


class AppState:
    """Shared application state."""

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        self.config = config or OrchestratorConfig()
        self.event_bus = EventBus()
        self.ws_manager = WebSocketManager(self.event_bus)
        self.artifact_store = ArtifactStore(tempfile.mkdtemp(prefix="orch-"))
        self.pipelines: dict[str, PipelineStatus] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}

        # Adapter factory with mock fallback for missing CLIs
        self._factory = AdapterFactory(mock_fallback=True)

        # Agent tracker for real-time status
        self.agent_tracker = AgentTracker(self.event_bus)

        # Resolve agent definitions from config or defaults
        self._agent_defs = self.config.agents or dict(_DEFAULT_AGENTS)

        # Register agents in tracker
        for name, agent_def in self._agent_defs.items():
            self.agent_tracker.register(name, agent_def.cli)

        # Cached adapters (populated on first pipeline run)
        self._adapters: dict[str, Any] = {}

    async def _get_adapters(self) -> tuple[Any, Any, Any]:
        """Lazily create adapters from config."""
        if not self._adapters:
            roles = ["planner", "implementer", "reviewer"]
            for role in roles:
                agent_def = self._agent_defs.get(role)
                if agent_def is None:
                    # Fallback: use first/second/third agent from config
                    keys = list(self._agent_defs.keys())
                    idx = roles.index(role)
                    agent_def = self._agent_defs.get(
                        keys[idx] if idx < len(keys) else keys[0],
                        _DEFAULT_AGENTS[role],
                    )
                self._adapters[role] = await self._factory.create(role, agent_def)

        return (
            self._adapters["planner"],
            self._adapters["implementer"],
            self._adapters["reviewer"],
        )

    async def run_pipeline(
        self, task_id: str, task: str, *, target_repo: str | None = None
    ) -> None:
        """Run a pipeline in background.

        Args:
            task_id: Unique identifier for this pipeline run.
            task: The task description.
            target_repo: Git repo path where CLI agents should work.
                         When set, a worktree is created per-pipeline.
        """
        self.agent_tracker.reset_all()

        await self.event_bus.publish(
            OrchestratorEvent(
                type=EventType.PIPELINE_STARTED,
                task_id=task_id,
                data={"task_id": task_id},
            )
        )

        self.pipelines[task_id] = PipelineStatus(
            task_id=task_id, task=task, status=TaskStatus.RUNNING
        )

        # Worktree isolation: create a worktree for this pipeline
        worktree_path: str | None = None
        worktree_mgr = None
        if target_repo:
            from orchestrator.worktree.manager import WorktreeManager

            worktree_mgr = WorktreeManager(target_repo)
            worktree_path = await worktree_mgr.create(task_id, "pipeline")

        try:
            planner, implementer, reviewer = await self._get_adapters()

            graph = build_graph(
                planner,
                implementer,
                reviewer,
                self.artifact_store,
                self.event_bus,
                task_id=task_id,
                cwd=worktree_path,
            )

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

            # Collect file changes from worktree
            if worktree_path:
                from orchestrator.worktree.collector import FileDiffCollector

                after = FileDiffCollector.snapshot(worktree_path)
                # Empty before = everything is "created"
                changes = FileDiffCollector.diff({}, after)
                if changes:
                    contents = FileDiffCollector.collect_changes(worktree_path, changes)
                    for filepath, content in contents.items():
                        self.artifact_store.save(
                            f"files/{filepath}",
                            content,
                            task_id=task_id,
                        )

            status = self.pipelines[task_id]
            status.status = (
                TaskStatus.COMPLETED if result["status"] == "reviewed" else TaskStatus.FAILED
            )
            status.error = result.get("error", "")
            status.artifacts = self.artifact_store.list_artifacts()
            status.messages = result.get("messages", [])

            await self.event_bus.publish(
                OrchestratorEvent(
                    type=EventType.PIPELINE_COMPLETED
                    if status.status == TaskStatus.COMPLETED
                    else EventType.PIPELINE_FAILED,
                    task_id=task_id,
                    data={"task_id": task_id, "status": status.status.value},
                )
            )
        except Exception as e:
            pipeline = self.pipelines.get(task_id)
            if pipeline:
                pipeline.status = TaskStatus.FAILED
                pipeline.error = str(e)
            await self.event_bus.publish(
                OrchestratorEvent(
                    type=EventType.PIPELINE_FAILED,
                    task_id=task_id,
                    data={"task_id": task_id, "error": str(e)},
                )
            )
        finally:
            # Cleanup worktree (best-effort)
            if worktree_mgr and worktree_path:
                with contextlib.suppress(Exception):
                    await worktree_mgr.cleanup(task_id, "pipeline")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app(config_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config_with_defaults(
        Path(config_path) if config_path else None
    )

    app = FastAPI(
        title="LLM Team Orchestrator",
        version="0.4.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state = AppState(config)
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

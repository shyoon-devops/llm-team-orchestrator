"""★ PoC 전용 — FastAPI REST API routes."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from pydantic import BaseModel

if TYPE_CHECKING:
    from orchestrator.web.app import AppState


class TaskSubmission(BaseModel):
    task: str
    target_repo: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    task: str
    status: str


def create_router(state: AppState) -> APIRouter:
    """Create API router with shared state."""
    router = APIRouter(prefix="/api")

    @router.post("/tasks", response_model=TaskResponse)
    async def submit_task(submission: TaskSubmission) -> dict[str, str]:
        task_id = str(uuid.uuid4())[:8]
        bg_task = asyncio.create_task(
            state.run_pipeline(task_id, submission.task, target_repo=submission.target_repo)
        )
        state._tasks[task_id] = bg_task
        return {"task_id": task_id, "task": submission.task, "status": "running"}

    @router.get("/tasks")
    async def list_tasks() -> list[dict[str, Any]]:
        return [p.model_dump() for p in state.pipelines.values()]

    @router.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        pipeline = state.pipelines.get(task_id)
        if not pipeline:
            return {"error": "not found"}
        return pipeline.model_dump()

    @router.get("/agents")
    async def list_agents() -> list[dict[str, str]]:
        return state.agent_tracker.get_all()

    @router.get("/artifacts")
    async def list_artifacts() -> list[str]:
        return state.artifact_store.list_artifacts()

    @router.get("/artifacts/{key:path}")
    async def get_artifact(key: str) -> dict[str, str]:
        try:
            content = state.artifact_store.load(key)
            return {"key": key, "content": content}
        except Exception:
            return {"error": f"Artifact not found: {key}"}

    @router.get("/events")
    async def get_events() -> list[dict[str, Any]]:
        return [e.model_dump() for e in state.event_bus.history]

    # ── Board endpoints (★ PoC 전용) ─────────────────────────────

    @router.get("/board")
    async def get_board_state() -> dict[str, Any]:
        """Get kanban board state grouped by column."""
        if hasattr(state, "task_board") and state.task_board:
            result: dict[str, Any] = state.task_board.get_board_state()
            return result
        return {}

    @router.get("/board/lanes")
    async def get_lanes() -> list[str]:
        """List available lanes."""
        if hasattr(state, "task_board") and state.task_board:
            return list(state.task_board._lanes.keys())
        return []

    @router.get("/board/tasks/{task_id}")
    async def get_board_task(task_id: str) -> dict[str, Any]:
        """Get a specific task from the board."""
        if hasattr(state, "task_board") and state.task_board:
            task = state.task_board.get_task(task_id)
            if task:
                dump: dict[str, Any] = task.model_dump()
                return dump
        return {"error": "not found"}

    return router

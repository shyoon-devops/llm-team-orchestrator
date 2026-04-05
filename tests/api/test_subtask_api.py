"""Tests for V2-3: subtask detail API — 4 new endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.api.app import create_app
from orchestrator.api.deps import set_engine
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.models.pipeline import (
    FileChange,
    Pipeline,
    PipelineStatus,
    SubTask,
    WorkerResult,
)
from orchestrator.core.queue.models import TaskItem, TaskState


@pytest.fixture
async def engine(tmp_path: Any) -> Any:
    """테스트용 OrchestratorEngine 인스턴스."""
    config = OrchestratorConfig(
        checkpoint_enabled=True,
        checkpoint_db_path=str(tmp_path / "test_checkpoints.sqlite"),
    )
    eng = OrchestratorEngine(config=config)
    await eng.start()
    yield eng
    await eng.shutdown()


@pytest.fixture
async def async_client(engine: OrchestratorEngine) -> Any:
    """httpx AsyncClient for testing."""
    app = create_app()
    app.state.engine = engine
    set_engine(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _seed_pipeline(engine: OrchestratorEngine) -> Pipeline:
    """Seed a pipeline with subtasks, board tasks, and worker results."""
    pipeline = Pipeline(
        task_id="pipe-test-001",
        task="Build a web app",
        status=PipelineStatus.COMPLETED,
        team_preset="feature-team",
        subtasks=[
            SubTask(
                id="sub-arch",
                description="Design architecture",
                assigned_preset="architect",
                depends_on=[],
            ),
            SubTask(
                id="sub-impl",
                description="Implement features",
                assigned_preset="implementer",
                depends_on=["sub-arch"],
            ),
        ],
        results=[
            WorkerResult(
                subtask_id="sub-arch",
                executor_type="cli",
                output="Architecture: use React + Express",
                files_changed=[
                    FileChange(
                        path="docs/architecture.md",
                        change_type="added",
                        content="# Architecture\nReact + Express",
                    )
                ],
            ),
            WorkerResult(
                subtask_id="sub-impl",
                executor_type="cli",
                output="Implementation complete",
                files_changed=[
                    FileChange(
                        path="src/app.tsx",
                        change_type="added",
                        content="export function App() { return <div>Hello</div>; }",
                    ),
                    FileChange(
                        path="src/server.ts",
                        change_type="added",
                        content="import express from 'express';",
                    ),
                ],
            ),
        ],
        completed_at=datetime.utcnow(),
    )
    engine._pipelines[pipeline.task_id] = pipeline

    # Seed board tasks
    arch_task = TaskItem(
        id="sub-arch",
        title="Design architecture",
        description="Design architecture",
        lane="architect",
        state=TaskState.DONE,
        depends_on=[],
        pipeline_id="pipe-test-001",
        result="Architecture: use React + Express",
        started_at=datetime(2026, 1, 1, 10, 0, 0),
        completed_at=datetime(2026, 1, 1, 10, 5, 0),
    )
    impl_task = TaskItem(
        id="sub-impl",
        title="Implement features",
        description="Implement features",
        lane="implementer",
        state=TaskState.DONE,
        depends_on=["sub-arch"],
        pipeline_id="pipe-test-001",
        result="Implementation complete",
        started_at=datetime(2026, 1, 1, 10, 5, 0),
        completed_at=datetime(2026, 1, 1, 10, 15, 0),
    )
    engine._board._tasks["sub-arch"] = arch_task
    engine._board._tasks["sub-impl"] = impl_task

    return pipeline


# ── GET /api/tasks/{id}/subtasks ──────────────────────────────


async def test_list_subtasks(engine: OrchestratorEngine, async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/subtasks returns subtask list with board state."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/subtasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "pipe-test-001"
    assert len(data["subtasks"]) == 2

    arch = data["subtasks"][0]
    assert arch["id"] == "sub-arch"
    assert arch["state"] == "done"
    assert arch["result"] == "Architecture: use React + Express"
    assert arch["assigned_preset"] == "architect"

    impl = data["subtasks"][1]
    assert impl["id"] == "sub-impl"
    assert impl["state"] == "done"
    assert impl["depends_on"] == ["sub-arch"]


async def test_list_subtasks_404(async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/subtasks returns 404 for unknown pipeline."""
    resp = await async_client.get("/api/tasks/nonexistent/subtasks")
    assert resp.status_code == 404


# ── GET /api/tasks/{id}/subtasks/{sub_id} ──────────────────────


async def test_get_subtask_detail(engine: OrchestratorEngine, async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/subtasks/{sub_id} returns subtask detail + result."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/subtasks/sub-arch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "sub-arch"
    assert data["state"] == "done"
    assert data["result"] == "Architecture: use React + Express"
    assert len(data["files_changed"]) == 1
    assert data["files_changed"][0]["path"] == "docs/architecture.md"


async def test_get_subtask_detail_404_pipeline(async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/subtasks/{sub_id} returns 404 for unknown pipeline."""
    resp = await async_client.get("/api/tasks/nonexistent/subtasks/sub-arch")
    assert resp.status_code == 404


async def test_get_subtask_detail_404_subtask(
    engine: OrchestratorEngine, async_client: AsyncClient
) -> None:
    """GET /api/tasks/{id}/subtasks/{sub_id} returns 404 for unknown subtask."""
    _seed_pipeline(engine)
    resp = await async_client.get("/api/tasks/pipe-test-001/subtasks/nonexistent")
    assert resp.status_code == 404


# ── GET /api/tasks/{id}/files ──────────────────────────────────


async def test_list_task_files(engine: OrchestratorEngine, async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/files returns deduplicated file list."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/files")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "pipe-test-001"
    # 3 files total: architecture.md, app.tsx, server.ts
    assert len(data["files"]) == 3
    paths = [f["path"] for f in data["files"]]
    assert "docs/architecture.md" in paths
    assert "src/app.tsx" in paths
    assert "src/server.ts" in paths


async def test_list_task_files_404(async_client: AsyncClient) -> None:
    """GET /api/tasks/{id}/files returns 404 for unknown pipeline."""
    resp = await async_client.get("/api/tasks/nonexistent/files")
    assert resp.status_code == 404


# ── GET /api/tasks/{id}/files/{path} ───────────────────────────


async def test_get_task_file_content(
    engine: OrchestratorEngine, async_client: AsyncClient
) -> None:
    """GET /api/tasks/{id}/files/{path} returns file content."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/files/docs/architecture.md")
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "docs/architecture.md"
    assert data["change_type"] == "added"
    assert "Architecture" in data["content"]
    assert data["subtask_id"] == "sub-arch"


async def test_get_task_file_content_nested_path(
    engine: OrchestratorEngine, async_client: AsyncClient
) -> None:
    """GET /api/tasks/{id}/files/{path} works with nested paths."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/files/src/app.tsx")
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "src/app.tsx"
    assert "App" in data["content"]


async def test_get_task_file_not_found(
    engine: OrchestratorEngine, async_client: AsyncClient
) -> None:
    """GET /api/tasks/{id}/files/{path} returns 404 for unknown file."""
    _seed_pipeline(engine)

    resp = await async_client.get("/api/tasks/pipe-test-001/files/nonexistent.txt")
    assert resp.status_code == 404

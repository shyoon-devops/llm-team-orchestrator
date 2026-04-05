"""★ PoC 전용 — HTTP E2E test through the web layer.

Submits a task via POST /api/tasks, waits for the mock pipeline to complete,
then verifies events, artifacts, task status, and agent statuses via GET endpoints.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from orchestrator.config.schema import AgentDef, OrchestratorConfig
from orchestrator.web.app import AppState, create_app
from orchestrator.web.routes import create_router


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    """Config with all-mock agents (no real CLI calls)."""
    return OrchestratorConfig(
        agents={
            "planner": AgentDef(cli="mock", role="architect", timeout=30),
            "implementer": AgentDef(cli="mock", role="engineer", timeout=30),
            "reviewer": AgentDef(cli="mock", role="reviewer", timeout=30),
        }
    )


@pytest.fixture
def app(mock_config: OrchestratorConfig) -> FastAPI:
    """Create a FastAPI app wired to mock config."""
    application = create_app()
    state = AppState(mock_config)
    application.state.app_state = state
    # Re-create router with mock state
    application.routes.clear()
    router = create_router(state)
    application.include_router(router)

    # Re-add the websocket endpoint (cleared above)
    from fastapi import WebSocket, WebSocketDisconnect

    @application.websocket("/ws/events")
    async def websocket_events(ws: WebSocket) -> None:
        await state.ws_manager.connect(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            state.ws_manager.disconnect(ws)

    return application


async def _wait_for_pipeline(app: FastAPI, timeout: float = 10.0) -> None:
    """Wait until all background pipeline tasks complete."""
    state: AppState = app.state.app_state
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        # Check if any tasks are still running
        pending = [t for t in state._tasks.values() if not t.done()]
        if not pending:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("Pipeline did not complete within timeout")


class TestHTTPE2E:
    """Full HTTP E2E: submit task -> wait -> verify all endpoints."""

    async def test_submit_and_verify_pipeline_completion(
        self, app: FastAPI
    ) -> None:
        """POST /api/tasks -> pipeline runs -> GET endpoints reflect results."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Submit a task
            resp = await client.post(
                "/api/tasks", json={"task": "Build a hello world REST API"}
            )
            assert resp.status_code == 200
            data = resp.json()
            task_id = data["task_id"]
            assert data["status"] == "running"
            assert data["task"] == "Build a hello world REST API"

            # 2. Wait for the mock pipeline to finish
            await _wait_for_pipeline(app)

            # 3. GET /api/tasks — verify task appears with completed status
            resp = await client.get("/api/tasks")
            assert resp.status_code == 200
            tasks: list[dict[str, Any]] = resp.json()
            assert len(tasks) >= 1
            task_entry = next(t for t in tasks if t["task_id"] == task_id)
            assert task_entry["status"] == "completed"
            assert task_entry["error"] == ""

            # 4. GET /api/tasks/{id} — verify single task detail
            resp = await client.get(f"/api/tasks/{task_id}")
            assert resp.status_code == 200
            detail = resp.json()
            assert detail["status"] == "completed"
            assert len(detail["messages"]) == 3  # plan + implement + review
            assert len(detail["artifacts"]) >= 3

            # 5. GET /api/events — verify pipeline events were emitted
            resp = await client.get("/api/events")
            assert resp.status_code == 200
            events: list[dict[str, Any]] = resp.json()
            event_types = [e["type"] for e in events]
            assert "pipeline.started" in event_types
            assert "node.started" in event_types
            assert "node.completed" in event_types
            assert "pipeline.completed" in event_types

            # Verify event ordering: started before completed
            started_idx = event_types.index("pipeline.started")
            completed_idx = event_types.index("pipeline.completed")
            assert started_idx < completed_idx

            # 6. GET /api/agents — verify agent statuses
            resp = await client.get("/api/agents")
            assert resp.status_code == 200
            agents: list[dict[str, Any]] = resp.json()
            assert len(agents) == 3
            agent_map = {a["id"]: a for a in agents}
            assert "planner" in agent_map
            assert "implementer" in agent_map
            assert "reviewer" in agent_map
            # After completion, all agents should be in completed state
            for name in ("planner", "implementer", "reviewer"):
                assert agent_map[name]["status"] == "completed"
                assert agent_map[name]["provider"] == "mock"

            # 7. GET /api/artifacts — verify artifacts were created
            resp = await client.get("/api/artifacts")
            assert resp.status_code == 200
            artifacts: list[str] = resp.json()
            assert "plan.md" in artifacts
            assert "implementation.md" in artifacts
            assert "review.md" in artifacts

            # 8. GET /api/artifacts/{key} — verify artifact content is non-empty
            resp = await client.get("/api/artifacts/plan.md")
            assert resp.status_code == 200
            artifact_data = resp.json()
            assert "content" in artifact_data
            assert len(artifact_data["content"]) > 0

    async def test_events_contain_node_details(self, app: FastAPI) -> None:
        """Verify node events carry the correct node names."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/tasks", json={"task": "Implement user auth"})
            await _wait_for_pipeline(app)

            resp = await client.get("/api/events")
            events = resp.json()

            # Collect node names from node.started / node.completed events
            node_events = [
                e for e in events if e["type"] in ("node.started", "node.completed")
            ]
            node_names = {e.get("node", "") for e in node_events}
            # All three nodes should have emitted events
            assert "plan" in node_names
            assert "implement" in node_names
            assert "review" in node_names

    async def test_multiple_tasks_sequential(self, app: FastAPI) -> None:
        """Submit multiple tasks sequentially and verify all complete."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            task_ids: list[str] = []
            for i in range(3):
                resp = await client.post(
                    "/api/tasks", json={"task": f"Task {i}: build feature"}
                )
                assert resp.status_code == 200
                task_ids.append(resp.json()["task_id"])
                await _wait_for_pipeline(app)

            # All tasks should be listed
            resp = await client.get("/api/tasks")
            tasks = resp.json()
            assert len(tasks) == 3

            # All should have completed
            for t in tasks:
                assert t["status"] == "completed"

    async def test_empty_state_before_task(self, app: FastAPI) -> None:
        """Before any task is submitted, all GET endpoints return empty."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tasks")
            assert resp.json() == []

            resp = await client.get("/api/events")
            assert resp.json() == []

            resp = await client.get("/api/artifacts")
            assert resp.json() == []

            # Agents should be registered but idle
            resp = await client.get("/api/agents")
            agents = resp.json()
            assert len(agents) == 3
            for a in agents:
                assert a["status"] == "idle"

"""★ PoC 전용 — Unit tests for FastAPI web backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator.config.schema import AgentDef, OrchestratorConfig
from orchestrator.web.app import create_app


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    """Config with all-mock agents (no real CLI health checks)."""
    return OrchestratorConfig(
        agents={
            "planner": AgentDef(cli="mock", role="architect", timeout=30),
            "implementer": AgentDef(cli="mock", role="engineer", timeout=30),
            "reviewer": AgentDef(cli="mock", role="reviewer", timeout=30),
        }
    )


@pytest.fixture
def client(mock_config: OrchestratorConfig) -> TestClient:
    app = create_app()
    # Override state with mock config to avoid real CLI calls
    from orchestrator.web.app import AppState

    app.state.app_state = AppState(mock_config)
    from orchestrator.web.routes import create_router

    # Re-create router with new state
    app.routes.clear()
    router = create_router(app.state.app_state)
    app.include_router(router)
    return TestClient(app)


class TestWebAPI:
    def test_list_tasks_empty(self, client: TestClient) -> None:
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_submit_task(self, client: TestClient) -> None:
        response = client.post("/api/tasks", json={"task": "implement auth"})
        assert response.status_code == 200
        data = response.json()
        assert data["task"] == "implement auth"
        assert data["status"] == "running"
        assert "task_id" in data

    def test_list_agents_from_tracker(self, client: TestClient) -> None:
        """Agents should come from AgentTracker (not hardcoded)."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3
        names = {a["id"] for a in agents}
        assert "planner" in names
        assert "implementer" in names
        assert "reviewer" in names
        for agent in agents:
            assert "status" in agent
            assert "provider" in agent

    def test_agents_have_provider_from_config(self, client: TestClient) -> None:
        """Agent providers should match mock config."""
        response = client.get("/api/agents")
        agents = {a["id"]: a for a in response.json()}
        assert agents["planner"]["provider"] == "mock"

    def test_list_artifacts_empty(self, client: TestClient) -> None:
        response = client.get("/api/artifacts")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_events_empty(self, client: TestClient) -> None:
        response = client.get("/api/events")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_nonexistent_task(self, client: TestClient) -> None:
        response = client.get("/api/tasks/nonexistent")
        assert response.status_code == 200
        assert response.json()["error"] == "not found"

    def test_get_nonexistent_artifact(self, client: TestClient) -> None:
        response = client.get("/api/artifacts/nonexistent.md")
        assert response.status_code == 200
        assert "error" in response.json()

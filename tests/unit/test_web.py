"""★ PoC 전용 — Unit tests for FastAPI web backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator.web.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
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

    def test_list_agents(self, client: TestClient) -> None:
        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3

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

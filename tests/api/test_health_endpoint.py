"""Tests for /api/health endpoint."""


async def test_health_check(async_client):
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_list_tasks_empty(async_client):
    response = await async_client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_submit_task(async_client):
    response = await async_client.post(
        "/api/tasks",
        json={"task": "build JWT"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["task"] == "build JWT"
    assert "task_id" in data


async def test_submit_empty_task(async_client):
    response = await async_client.post(
        "/api/tasks",
        json={"task": ""},
    )
    assert response.status_code == 422  # validation error


async def test_get_task_not_found(async_client):
    response = await async_client.get("/api/tasks/nonexistent")
    assert response.status_code == 404

"""Tests for preset API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.api.app import create_app
from orchestrator.api.deps import set_engine
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.presets.models import (
    AgentPreset,
    PersonaDef,
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)


@pytest.fixture
async def engine_with_presets(tmp_path):
    """OrchestratorEngine with some presets loaded, using a temp directory."""
    config = OrchestratorConfig(
        preset_dirs=[str(tmp_path / "presets")],
    )
    engine = OrchestratorEngine(config=config)
    engine.save_agent_preset(
        AgentPreset(
            name="test-architect",
            description="Test architect",
            persona=PersonaDef(role="Architect", goal="Design"),
            preferred_cli="claude",
        )
    )
    engine.save_agent_preset(
        AgentPreset(
            name="test-implementer",
            description="Test implementer",
            persona=PersonaDef(role="Developer", goal="Implement"),
            preferred_cli="codex",
        )
    )
    engine.save_team_preset(
        TeamPreset(
            name="test-team",
            description="Test team",
            agents={
                "arch": TeamAgentDef(preset="test-architect"),
                "dev": TeamAgentDef(preset="test-implementer"),
            },
            tasks={
                "design": TeamTaskDef(description="Design", agent="arch"),
                "implement": TeamTaskDef(
                    description="Implement",
                    agent="dev",
                    depends_on=["design"],
                ),
            },
            workflow="dag",
        )
    )
    return engine


@pytest.fixture
async def client(engine_with_presets):
    """httpx AsyncClient with presets."""
    app = create_app()
    app.state.engine = engine_with_presets
    set_engine(engine_with_presets)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestListAgentPresets:
    async def test_list_agent_presets(self, client):
        resp = await client.get("/api/presets/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        names = [p["name"] for p in data["presets"]]
        assert "test-architect" in names
        assert "test-implementer" in names

    async def test_list_agent_presets_sorted(self, client):
        resp = await client.get("/api/presets/agents")
        data = resp.json()
        names = [p["name"] for p in data["presets"]]
        assert names == sorted(names)


class TestGetAgentPreset:
    async def test_get_agent_preset_found(self, client):
        resp = await client.get("/api/presets/agents/test-architect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-architect"
        assert data["persona"]["role"] == "Architect"

    async def test_get_agent_preset_not_found(self, client):
        resp = await client.get("/api/presets/agents/nonexistent")
        assert resp.status_code == 404


class TestCreateAgentPreset:
    async def test_create_agent_preset(self, client):
        resp = await client.post(
            "/api/presets/agents",
            json={
                "name": "new-agent",
                "persona": {
                    "role": "New Agent",
                    "goal": "Be new",
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-agent"
        assert data["persona"]["role"] == "New Agent"

    async def test_create_agent_preset_duplicate(self, client):
        resp = await client.post(
            "/api/presets/agents",
            json={
                "name": "test-architect",
                "persona": {
                    "role": "Dup",
                    "goal": "Dup",
                },
            },
        )
        assert resp.status_code == 409

    async def test_create_agent_preset_invalid(self, client):
        resp = await client.post(
            "/api/presets/agents",
            json={
                "name": "bad agent name with spaces",
                "persona": {
                    "role": "Bad",
                    "goal": "Bad",
                },
            },
        )
        assert resp.status_code == 422  # validation error


class TestListTeamPresets:
    async def test_list_team_presets(self, client):
        resp = await client.get("/api/presets/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        names = [p["name"] for p in data["presets"]]
        assert "test-team" in names

    async def test_team_preset_structure(self, client):
        resp = await client.get("/api/presets/teams")
        data = resp.json()
        team = data["presets"][0]
        assert "agents" in team
        assert "tasks" in team
        assert "workflow" in team


class TestGetTeamPreset:
    async def test_get_team_preset_found(self, client):
        resp = await client.get("/api/presets/teams/test-team")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-team"
        assert "arch" in data["agents"]
        assert "design" in data["tasks"]

    async def test_get_team_preset_not_found(self, client):
        resp = await client.get("/api/presets/teams/nonexistent")
        assert resp.status_code == 404


class TestCreateTeamPreset:
    async def test_create_team_preset(self, client):
        resp = await client.post(
            "/api/presets/teams",
            json={
                "name": "new-team",
                "agents": {
                    "dev": {"preset": "implementer"},
                },
                "tasks": {
                    "code": {
                        "description": "Write code",
                        "agent": "dev",
                    },
                },
                "workflow": "sequential",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-team"
        assert data["workflow"] == "sequential"

    async def test_create_team_preset_duplicate(self, client):
        resp = await client.post(
            "/api/presets/teams",
            json={
                "name": "test-team",
                "agents": {"dev": {"preset": "implementer"}},
                "tasks": {"code": {"description": "Code", "agent": "dev"}},
            },
        )
        assert resp.status_code == 409

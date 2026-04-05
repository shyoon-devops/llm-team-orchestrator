"""Tests for preset models — PersonaDef, AgentPreset, TeamPreset."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.core.presets.models import (
    AgentLimits,
    AgentPreset,
    MCPServerDef,
    PersonaDef,
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
    ToolAccess,
)


class TestPersonaDef:
    def test_create_minimal(self):
        persona = PersonaDef(role="Developer", goal="Write code")
        assert persona.role == "Developer"
        assert persona.goal == "Write code"
        assert persona.backstory == ""
        assert persona.constraints == []

    def test_create_full(self):
        persona = PersonaDef(
            role="시니어 백엔드 개발자",
            goal="견고한 코드를 구현한다",
            backstory="10년 경력",
            constraints=["테스트 필수", "타입 힌트 필수"],
        )
        assert persona.backstory == "10년 경력"
        assert len(persona.constraints) == 2

    def test_to_system_prompt_minimal(self):
        persona = PersonaDef(role="Architect", goal="Design systems")
        prompt = persona.to_system_prompt()
        assert "당신의 역할: Architect" in prompt
        assert "목표: Design systems" in prompt
        assert "배경:" not in prompt
        assert "제약 조건:" not in prompt

    def test_to_system_prompt_full(self):
        persona = PersonaDef(
            role="Developer",
            goal="Write code",
            backstory="Senior dev",
            constraints=["Test required", "Type hints"],
        )
        prompt = persona.to_system_prompt()
        assert "배경: Senior dev" in prompt
        assert "제약 조건:" in prompt
        assert "- Test required" in prompt
        assert "- Type hints" in prompt

    def test_role_required(self):
        with pytest.raises(ValidationError):
            PersonaDef(role="", goal="Write code")

    def test_goal_required(self):
        with pytest.raises(ValidationError):
            PersonaDef(role="Dev", goal="")


class TestToolAccess:
    def test_defaults(self):
        tools = ToolAccess()
        assert tools.allowed == []
        assert tools.disallowed == []

    def test_with_values(self):
        tools = ToolAccess(
            allowed=["Read", "Write"],
            disallowed=["WebSearch"],
        )
        assert tools.allowed == ["Read", "Write"]
        assert tools.disallowed == ["WebSearch"]


class TestAgentLimits:
    def test_defaults(self):
        limits = AgentLimits()
        assert limits.timeout == 300
        assert limits.max_turns == 50
        assert limits.max_iterations == 10

    def test_custom_values(self):
        limits = AgentLimits(timeout=600, max_turns=100, max_iterations=20)
        assert limits.timeout == 600

    def test_timeout_range(self):
        with pytest.raises(ValidationError):
            AgentLimits(timeout=5)  # min is 10

        with pytest.raises(ValidationError):
            AgentLimits(timeout=7200)  # max is 3600


class TestMCPServerDef:
    def test_create(self):
        server = MCPServerDef(
            command="npx",
            args=["-y", "@anthropic/mcp-server-elasticsearch"],
            env={"ES_URL": "http://localhost:9200"},
        )
        assert server.command == "npx"
        assert len(server.args) == 2
        assert server.env["ES_URL"] == "http://localhost:9200"

    def test_command_required(self):
        with pytest.raises(ValidationError):
            MCPServerDef(command="")


class TestAgentPreset:
    def test_create_minimal(self):
        preset = AgentPreset(
            name="test-agent",
            persona=PersonaDef(role="Dev", goal="Code"),
        )
        assert preset.name == "test-agent"
        assert preset.execution_mode == "cli"
        assert preset.preferred_cli == "claude"
        assert preset.fallback_cli == []
        assert preset.model is None
        assert preset.limits.timeout == 300

    def test_name_pattern_valid(self):
        AgentPreset(name="my-agent", persona=PersonaDef(role="Dev", goal="Code"))
        AgentPreset(name="agent123", persona=PersonaDef(role="Dev", goal="Code"))
        AgentPreset(name="elk-analyst", persona=PersonaDef(role="Dev", goal="Code"))

    def test_name_pattern_invalid(self):
        with pytest.raises(ValidationError):
            AgentPreset(name="My Agent", persona=PersonaDef(role="Dev", goal="Code"))

        with pytest.raises(ValidationError):
            AgentPreset(name="UPPER", persona=PersonaDef(role="Dev", goal="Code"))

    def test_execution_mode_mcp(self):
        preset = AgentPreset(
            name="mcp-agent",
            persona=PersonaDef(role="Analyst", goal="Analyze"),
            execution_mode="mcp",
            preferred_cli=None,
            mcp_servers={
                "es": MCPServerDef(command="npx", args=["-y", "mcp-es"]),
            },
        )
        assert preset.execution_mode == "mcp"
        assert "es" in preset.mcp_servers

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            AgentPreset(
                name="test",
                persona=PersonaDef(role="Dev", goal="Code"),
                unknown_field="bad",  # type: ignore[call-arg]
            )


class TestTeamAgentDef:
    def test_create_minimal(self):
        agent_def = TeamAgentDef(preset="implementer")
        assert agent_def.preset == "implementer"
        assert agent_def.overrides == {}

    def test_with_overrides(self):
        agent_def = TeamAgentDef(
            preset="architect",
            overrides={"limits": {"timeout": 600}},
        )
        assert agent_def.overrides["limits"]["timeout"] == 600


class TestTeamTaskDef:
    def test_create_minimal(self):
        task = TeamTaskDef(description="Design API", agent="architect")
        assert task.description == "Design API"
        assert task.agent == "architect"
        assert task.depends_on == []

    def test_with_depends_on(self):
        task = TeamTaskDef(
            description="Implement",
            agent="implementer",
            depends_on=["design"],
        )
        assert task.depends_on == ["design"]


class TestTeamPreset:
    def test_create_valid(self):
        preset = TeamPreset(
            name="test-team",
            agents={"dev": TeamAgentDef(preset="implementer")},
            tasks={"code": TeamTaskDef(description="Write code", agent="dev")},
        )
        assert preset.name == "test-team"
        assert preset.workflow == "parallel"
        assert preset.synthesis_strategy == "narrative"

    def test_validate_task_agent_reference(self):
        with pytest.raises(ValidationError, match="agents에 정의되지 않음"):
            TeamPreset(
                name="bad-team",
                agents={"dev": TeamAgentDef(preset="implementer")},
                tasks={
                    "code": TeamTaskDef(description="Write", agent="nonexistent"),
                },
            )

    def test_validate_depends_on_reference(self):
        with pytest.raises(ValidationError, match="tasks에 정의되지 않음"):
            TeamPreset(
                name="bad-team",
                agents={"dev": TeamAgentDef(preset="implementer")},
                tasks={
                    "code": TeamTaskDef(
                        description="Write",
                        agent="dev",
                        depends_on=["nonexistent"],
                    ),
                },
            )

    def test_validate_self_dependency(self):
        with pytest.raises(ValidationError, match="자기 자신에 의존"):
            TeamPreset(
                name="bad-team",
                agents={"dev": TeamAgentDef(preset="implementer")},
                tasks={
                    "code": TeamTaskDef(
                        description="Write",
                        agent="dev",
                        depends_on=["code"],
                    ),
                },
            )

    def test_dag_workflow(self):
        preset = TeamPreset(
            name="dag-team",
            agents={
                "arch": TeamAgentDef(preset="architect"),
                "dev": TeamAgentDef(preset="implementer"),
                "rev": TeamAgentDef(preset="reviewer"),
            },
            tasks={
                "design": TeamTaskDef(description="Design", agent="arch"),
                "implement": TeamTaskDef(
                    description="Implement",
                    agent="dev",
                    depends_on=["design"],
                ),
                "review": TeamTaskDef(
                    description="Review",
                    agent="rev",
                    depends_on=["implement"],
                ),
            },
            workflow="dag",
            synthesis_strategy="structured",
        )
        assert preset.workflow == "dag"
        assert preset.synthesis_strategy == "structured"
        assert preset.tasks["implement"].depends_on == ["design"]

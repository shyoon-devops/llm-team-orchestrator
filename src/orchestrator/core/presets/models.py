"""Preset models — PersonaDef, AgentPreset, TeamPreset."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PersonaDef(BaseModel):
    """에이전트 페르소나 정의."""

    role: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1, max_length=500)
    backstory: str = Field(default="", max_length=2000)
    constraints: list[str] = Field(default_factory=list)

    def to_system_prompt(self) -> str:
        """페르소나를 시스템 프롬프트 문자열로 변환한다."""
        parts = [
            f"당신의 역할: {self.role}",
            f"목표: {self.goal}",
        ]
        if self.backstory:
            parts.append(f"배경: {self.backstory}")
        if self.constraints:
            constraints_text = "\n".join(f"- {c}" for c in self.constraints)
            parts.append(f"제약 조건:\n{constraints_text}")
        return "\n\n".join(parts)


class ToolAccess(BaseModel):
    """에이전트 도구 접근 제어."""

    allowed: list[str] = Field(default_factory=list)
    disallowed: list[str] = Field(default_factory=list)


class AgentLimits(BaseModel):
    """에이전트 실행 제한."""

    timeout: int = Field(default=300, ge=10, le=3600)
    max_turns: int = Field(default=50, ge=1, le=500)
    max_iterations: int = Field(default=10, ge=1, le=100)


class MCPServerDef(BaseModel):
    """MCP 서버 실행 정의."""

    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class AgentPreset(BaseModel):
    """에이전트 프리셋."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    persona: PersonaDef
    execution_mode: Literal["cli", "mcp"] = Field(default="cli")
    preferred_cli: Literal["claude", "codex", "gemini"] | None = Field(default="claude")
    fallback_cli: list[Literal["claude", "codex", "gemini"]] = Field(default_factory=list)
    model: str | None = Field(default=None)
    tools: ToolAccess = Field(default_factory=ToolAccess)
    mcp_servers: dict[str, MCPServerDef] = Field(default_factory=dict)
    limits: AgentLimits = Field(default_factory=AgentLimits)

    model_config = {"extra": "forbid"}


class TeamAgentDef(BaseModel):
    """팀 내 에이전트 정의."""

    preset: str = Field(..., min_length=1)
    overrides: dict[str, Any] = Field(default_factory=dict)


class TeamTaskDef(BaseModel):
    """팀 내 태스크 정의."""

    description: str = Field(..., min_length=1, max_length=2000)
    agent: str = Field(..., min_length=1)
    depends_on: list[str] = Field(default_factory=list)


class TeamPreset(BaseModel):
    """팀 프리셋."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str = Field(default="", max_length=500)
    agents: dict[str, TeamAgentDef] = Field(..., min_length=1)
    tasks: dict[str, TeamTaskDef] = Field(..., min_length=1)
    workflow: Literal["parallel", "sequential", "dag"] = Field(default="parallel")
    synthesis_strategy: Literal["narrative", "structured", "checklist"] = Field(
        default="narrative"
    )

    @model_validator(mode="after")
    def validate_task_agent_references(self) -> TeamPreset:
        """태스크의 agent 참조가 agents에 존재하는지 검증한다."""
        agent_names = set(self.agents.keys())
        for task_name, task_def in self.tasks.items():
            if task_def.agent not in agent_names:
                msg = (
                    f"태스크 '{task_name}'의 agent '{task_def.agent}'가 "
                    f"agents에 정의되지 않음. 사용 가능: {agent_names}"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_depends_on_references(self) -> TeamPreset:
        """태스크의 depends_on 참조가 tasks에 존재하는지 검증한다."""
        task_names = set(self.tasks.keys())
        for task_name, task_def in self.tasks.items():
            for dep in task_def.depends_on:
                if dep not in task_names:
                    msg = (
                        f"태스크 '{task_name}'의 depends_on '{dep}'가 "
                        f"tasks에 정의되지 않음. 사용 가능: {task_names}"
                    )
                    raise ValueError(msg)
                if dep == task_name:
                    msg = f"태스크 '{task_name}'이 자기 자신에 의존할 수 없음"
                    raise ValueError(msg)
        return self

    model_config = {"extra": "forbid"}

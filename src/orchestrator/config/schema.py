"""Pydantic models for YAML configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentDef(BaseModel):
    """Agent definition from YAML config."""

    cli: str  # "claude" | "codex" | "gemini"
    role: str = ""
    model: str = ""
    timeout: int = 300
    max_iterations: int = 10


class TaskDef(BaseModel):
    """Task definition from YAML config."""

    description: str
    agent: str  # references agents key
    depends_on: list[str] = Field(default_factory=list)
    priority: int = 1


class DashboardConfig(BaseModel):
    """Web dashboard configuration."""

    enabled: bool = True
    port: int = 3000
    host: str = "localhost"


class OrchestratorConfig(BaseModel):
    """Root configuration model."""

    max_parallel_agents: int = 4
    timeout_per_task: int = 600
    log_level: str = "info"
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    agents: dict[str, AgentDef] = Field(default_factory=dict)
    tasks: dict[str, TaskDef] = Field(default_factory=dict)

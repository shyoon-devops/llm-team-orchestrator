"""Core data models for the orchestrator."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AdapterConfig(BaseModel):
    """Configuration for a CLI adapter."""

    api_key: str = ""
    timeout: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0)
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Result from a CLI agent execution."""

    output: str
    exit_code: int
    duration_ms: int = 0
    tokens_used: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class TaskConfig(BaseModel):
    """Configuration for an orchestration task."""

    task: str
    planner: str = "claude"
    implementer: str = "claude"
    reviewer: str = "claude"
    timeout: int = Field(default=600, ge=1)
    max_retries: int = Field(default=3, ge=0)


class AgentStatus(StrEnum):
    """Agent execution status."""

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class TaskStatus(StrEnum):
    """Pipeline task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentProgress(BaseModel):
    """Real-time agent progress info."""

    agent_id: str
    provider: str
    status: AgentStatus = AgentStatus.IDLE
    current_node: str = ""
    tokens_used: int = 0
    elapsed_ms: int = 0


class PipelineStatus(BaseModel):
    """Full pipeline status for dashboard display."""

    task_id: str
    task: str
    status: TaskStatus = TaskStatus.PENDING
    agents: list[AgentProgress] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    messages: list[dict[str, object]] = Field(default_factory=list)
    error: str = ""

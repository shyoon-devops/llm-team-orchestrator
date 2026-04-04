"""Core data models for the orchestrator."""

from __future__ import annotations

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

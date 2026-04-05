"""Event type definitions for the orchestrator."""

from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Orchestrator event types."""

    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"
    AGENT_HEALTH_CHECK = "agent.health_check"
    AUTH_KEY_ROTATED = "auth.key_rotated"


class OrchestratorEvent(BaseModel):
    """Event emitted during orchestration."""

    type: EventType
    timestamp: float = Field(default_factory=time.time)
    node: str = ""
    task_id: str = ""
    data: dict[str, object] = Field(default_factory=dict)

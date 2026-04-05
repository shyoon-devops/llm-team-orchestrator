"""Task queue models for kanban-style work distribution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class TaskState(StrEnum):
    BACKLOG = "backlog"  # 의존성 대기
    TODO = "todo"  # 큐에 투입됨, 소비 가능
    IN_PROGRESS = "in_progress"  # agent가 작업 중
    DONE = "done"  # 완료
    FAILED = "failed"  # 실패 (retry 초과)


class TaskItem(BaseModel):
    """A single work item on the kanban board."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str
    description: str = ""
    lane: str  # "plan" | "implement" | "review" | custom
    state: TaskState = TaskState.BACKLOG
    priority: int = 0  # higher = more urgent
    depends_on: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    result: str = ""
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    pipeline_id: str = ""  # parent pipeline ID

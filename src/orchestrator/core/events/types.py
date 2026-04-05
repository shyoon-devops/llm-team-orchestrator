"""Event types and event model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """시스템 이벤트 유형.

    EventBus를 통해 발행되며, WebSocket으로 실시간 전달된다.
    각 이벤트는 OrchestratorEvent 인스턴스로 래핑된다.
    """

    # 파이프라인 생명주기
    PIPELINE_CREATED = "pipeline.created"
    PIPELINE_PLANNING = "pipeline.planning"
    PIPELINE_RUNNING = "pipeline.running"
    PIPELINE_SYNTHESIZING = "pipeline.synthesizing"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    PIPELINE_CANCELLED = "pipeline.cancelled"

    # 태스크 보드
    TASK_SUBMITTED = "task.submitted"
    TASK_READY = "task.ready"
    TASK_CLAIMED = "task.claimed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRYING = "task.retrying"

    # 에이전트 워커
    WORKER_STARTED = "worker.started"
    WORKER_STOPPED = "worker.stopped"
    WORKER_HEARTBEAT = "worker.heartbeat"

    # 에이전트 실행
    AGENT_EXECUTING = "agent.executing"
    AGENT_OUTPUT = "agent.output"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"

    # 폴백
    FALLBACK_TRIGGERED = "fallback.triggered"
    FALLBACK_SUCCEEDED = "fallback.succeeded"
    FALLBACK_EXHAUSTED = "fallback.exhausted"

    # Git worktree
    WORKTREE_CREATED = "worktree.created"
    WORKTREE_MERGED = "worktree.merged"
    WORKTREE_CLEANUP = "worktree.cleanup"
    WORKTREE_CONFLICT = "worktree.conflict"

    # 종합
    SYNTHESIS_STARTED = "synthesis.started"
    SYNTHESIS_COMPLETED = "synthesis.completed"

    # 시스템
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"


class OrchestratorEvent(BaseModel):
    """시스템 이벤트.

    EventBus에서 발행하고, 구독자(WebSocket, 로그, 대시보드)에 전달한다.
    모든 이벤트는 task_id로 파이프라인에 연결된다.
    """

    type: EventType = Field(
        ...,
        description="이벤트 유형",
    )
    task_id: str = Field(
        default="",
        description="관련 파이프라인 ID. 시스템 이벤트는 빈 문자열",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="이벤트 발생 시각 (UTC)",
    )
    node: str = Field(
        default="",
        description="이벤트 발생 노드/컴포넌트 이름",
        examples=["orchestrator", "worker-1", "claude-adapter"],
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="이벤트 페이로드. 이벤트 유형별로 구조가 다름",
    )

    model_config = {"frozen": True}

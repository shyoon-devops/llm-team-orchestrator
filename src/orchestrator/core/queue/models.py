"""Queue models — TaskState, TaskItem."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskState(StrEnum):
    """칸반 보드 태스크 상태.

    상태 전이 규칙:
    - BACKLOG -> TODO: 의존성 충족 시 자동 전이
    - TODO -> IN_PROGRESS: AgentWorker가 claim 시
    - IN_PROGRESS -> DONE: 성공 완료 시
    - IN_PROGRESS -> FAILED: 실패 시 (max_retries 초과)
    - IN_PROGRESS -> TODO: 실패 시 재시도 (retry_count < max_retries)
    """

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class TaskItem(BaseModel):
    """칸반 보드 태스크 아이템.

    TaskBoard에서 관리하는 개별 작업 단위.
    에이전트별 레인에 배치되고, AgentWorker가 소비한다.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="태스크 고유 ID. UUID4 형식",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="태스크 제목 (사람이 읽을 수 있는 짧은 설명)",
        examples=["JWT 미들웨어 구현"],
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="태스크 상세 설명. 에이전트에 프롬프트로 전달됨",
    )
    lane: str = Field(
        ...,
        min_length=1,
        description="칸반 레인 이름. 보통 에이전트 프리셋 이름과 동일",
        examples=["implementer", "architect"],
    )
    state: TaskState = Field(
        default=TaskState.BACKLOG,
        description="현재 태스크 상태",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="우선순위 (0=기본, 높을수록 우선)",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="선행 태스크 ID 목록. 모두 DONE이어야 TODO로 전이",
    )
    assigned_to: str | None = Field(
        default=None,
        description="현재 할당된 AgentWorker ID. None이면 미할당",
    )
    result: str = Field(
        default="",
        description="실행 결과 텍스트. DONE 시 AgentResult.output 저장",
    )
    error: str = Field(
        default="",
        description="마지막 에러 메시지. FAILED 시 저장",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="현재까지 재시도 횟수",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="최대 재시도 횟수. 초과 시 FAILED",
    )
    pipeline_id: str = Field(
        default="",
        description="이 태스크가 속한 Pipeline ID",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="태스크 생성 시각 (UTC)",
    )
    started_at: datetime | None = Field(
        default=None,
        description="IN_PROGRESS 전이 시각",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="DONE 또는 FAILED 전이 시각",
    )

    @field_validator("depends_on")
    @classmethod
    def validate_no_self_dependency(cls, v: list[str], info: Any) -> list[str]:
        """자기 자신에 대한 의존성을 검증한다."""
        task_id = info.data.get("id")
        if task_id and task_id in v:
            msg = f"태스크가 자기 자신에 의존할 수 없음: {task_id}"
            raise ValueError(msg)
        return v

    model_config = {"extra": "forbid"}

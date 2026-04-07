"""Pipeline and related models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PipelineStatus(StrEnum):
    """파이프라인 상태.

    상태 전이 규칙:
    - PENDING -> PLANNING: 태스크 분해 시작
    - PLANNING -> RUNNING: 서브태스크를 TaskBoard에 투입
    - RUNNING -> SYNTHESIZING: 모든 서브태스크 완료
    - SYNTHESIZING -> COMPLETED: 종합 보고서 생성 완료
    - RUNNING -> PARTIAL_FAILURE: 일부 서브태스크 실패
    - PARTIAL_FAILURE -> SYNTHESIZING: 부분 결과로 종합 진행
    - RUNNING -> FAILED: 모든 서브태스크 실패 또는 치명적 오류
    - * -> CANCELLED: 사용자 취소
    """

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubTask(BaseModel):
    """파이프라인 서브태스크.

    TeamPlanner가 분해한 개별 작업 단위.
    TaskBoard의 TaskItem과 1:1 대응되며, task_id로 연결된다.
    """

    id: str = Field(
        ...,
        description="서브태스크 고유 ID. UUID4 형식",
        examples=["sub-001"],
    )
    task_id: str = Field(
        default="",
        description="대응되는 TaskItem ID. TaskBoard에 투입 후 설정됨",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="서브태스크 설명. TaskItem.description으로 복사됨",
    )
    assigned_cli: Literal["claude", "codex", "gemini"] | None = Field(
        default=None,
        description="할당된 CLI. None이면 AgentPreset.preferred_cli 사용",
    )
    assigned_preset: str = Field(
        default="",
        description="할당된 AgentPreset 이름",
        examples=["implementer", "architect"],
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="우선순위 (0=기본, 높을수록 우선)",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="선행 서브태스크 ID 목록",
    )
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="서브태스크 현재 상태",
    )

    model_config = {"extra": "forbid"}


class FileChange(BaseModel):
    """파일 변경 정보.

    FileDiffCollector가 에이전트 실행 전후 스냅샷을 비교하여 생성한다.
    """

    path: str = Field(
        ...,
        min_length=1,
        description="변경된 파일의 상대 경로 (worktree 기준)",
        examples=["src/middleware/auth.ts"],
    )
    change_type: Literal["added", "modified", "deleted"] = Field(
        ...,
        description="변경 유형",
    )
    content: str = Field(
        default="",
        description="변경 후 파일 전체 내용. deleted인 경우 빈 문자열",
    )

    model_config = {"extra": "forbid"}


class WorkerResult(BaseModel):
    """서브태스크 실행 결과.

    AgentWorker가 서브태스크를 완료한 후 생성한다.
    AgentResult의 주요 필드를 포함하고, 파일 변경 정보를 추가한다.
    """

    subtask_id: str = Field(
        ...,
        description="대응되는 SubTask ID",
        examples=["sub-001"],
    )
    executor_type: Literal["cli", "mcp", "mock"] = Field(
        ...,
        description="사용된 실행기 유형",
    )
    cli: str | None = Field(
        default=None,
        description="사용된 CLI 이름. executor_type='cli'일 때만 유효",
        examples=["claude", "codex", "gemini"],
    )
    output: str = Field(
        default="",
        description="에이전트 출력 텍스트 (AgentResult.output에서 복사)",
    )
    files_changed: list[FileChange] = Field(
        default_factory=list,
        description="변경된 파일 목록. FileDiffCollector가 수집",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="소비된 토큰 수",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="실행 소요 시간 (밀리초)",
    )
    error: str = Field(
        default="",
        description="에러 메시지. 실패 시 저장",
    )

    model_config = {"extra": "forbid"}


class Pipeline(BaseModel):
    """태스크 파이프라인.

    사용자가 제출한 하나의 태스크에 대한 전체 생명주기를 추적한다.
    분해(planning) -> 실행(running) -> 종합(synthesizing) -> 완료(completed)

    API 응답의 핵심 엔티티이며, GET /api/tasks/{id}로 조회된다.
    """

    task_id: str = Field(
        ...,
        description="파이프라인 고유 ID. UUID4 형식",
        examples=["pipeline-550e8400"],
    )
    task: str = Field(
        ...,
        min_length=1,
        description="사용자가 제출한 원본 태스크 설명",
        examples=["JWT 인증 미들웨어 구현"],
    )
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="파이프라인 현재 상태",
    )
    team_preset: str = Field(
        default="",
        description="사용된 TeamPreset 이름. 빈 문자열이면 자동 구성",
    )
    target_repo: str = Field(
        default="",
        description="대상 리포지토리 경로. 코딩 태스크에서 사용",
        examples=["./my-project", "/home/user/project"],
    )
    subtasks: list[SubTask] = Field(
        default_factory=list,
        description="분해된 서브태스크 목록",
    )
    results: list[WorkerResult] = Field(
        default_factory=list,
        description="서브태스크 실행 결과 목록",
    )
    synthesis: str = Field(
        default="",
        description="Synthesizer가 생성한 종합 보고서",
    )
    workspace_paths: dict[str, str] = Field(
        default_factory=dict,
        description="에이전트별 워크스페이스 경로 (lane -> 디렉토리). target_repo 없을 때 tempdir 위치 확인용",
    )
    merged: bool = Field(
        default=False,
        description="worktree 변경사항이 target branch에 merge되었는지 여부",
    )
    error: str = Field(
        default="",
        description="파이프라인 레벨 에러 메시지",
    )
    started_at: datetime | None = Field(
        default=None,
        description="파이프라인 시작 시각 (PLANNING 전이 시)",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="파이프라인 완료 시각 (COMPLETED/FAILED/CANCELLED 전이 시)",
    )

    model_config = {"extra": "forbid"}

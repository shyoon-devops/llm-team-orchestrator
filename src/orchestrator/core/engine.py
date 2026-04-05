"""OrchestratorEngine — single entry point for the Core layer."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from orchestrator.core.adapters.factory import AdapterFactory
from orchestrator.core.auth.provider import EnvAuthProvider
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.synthesizer import Synthesizer
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.models.pipeline import Pipeline, PipelineStatus
from orchestrator.core.presets.models import AgentPreset, TeamPreset
from orchestrator.core.presets.registry import PresetRegistry
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.worker import AgentWorker
from orchestrator.core.utils import generate_id
from orchestrator.core.worktree.manager import WorktreeManager

logger = structlog.get_logger()


class OrchestratorEngine:
    """Core 계층의 단일 진입점.

    API 계층은 이 클래스만 의존한다.
    모든 하위 컴포넌트(TaskBoard, PresetRegistry, EventBus 등)를 조합하고,
    태스크 생명주기를 관리한다.
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
    ) -> None:
        """
        Args:
            config: 시스템 설정. None이면 환경 변수에서 자동 로딩.
        """
        self.config = config or OrchestratorConfig()
        self._event_bus = EventBus()
        self._board = TaskBoard(max_retries=self.config.default_max_retries)
        self._preset_registry = PresetRegistry(self.config.preset_dirs)
        self._auth_provider = EnvAuthProvider()
        self._adapter_factory = AdapterFactory(self._auth_provider)
        self._worktree_manager = WorktreeManager(self.config.worktree_base_dir)
        self._synthesizer = Synthesizer(model=self.config.synthesizer_model)
        self._pipelines: dict[str, Pipeline] = {}
        self._workers: dict[str, AgentWorker] = {}

    @property
    def event_bus(self) -> EventBus:
        """이벤트 버스를 반환한다."""
        return self._event_bus

    async def submit_task(
        self,
        task: str,
        *,
        team_preset: str | None = None,
        target_repo: str | None = None,
    ) -> Pipeline:
        """사용자 태스크를 제출하고 파이프라인을 생성하여 실행을 시작한다.

        Args:
            task: 사용자가 입력한 태스크 설명.
            team_preset: 사용할 TeamPreset 이름. None이면 자동 구성.
            target_repo: 대상 리포지토리 경로.

        Returns:
            생성된 파이프라인 (초기 상태: PENDING).

        Raises:
            ValueError: task가 빈 문자열인 경우.
            KeyError: team_preset이 존재하지 않는 경우.
        """
        if not task.strip():
            msg = "Task description cannot be empty"
            raise ValueError(msg)

        if team_preset is not None:
            # 존재 여부 검증
            self._preset_registry.load_team_preset(team_preset)

        task_id = generate_id("pipeline")
        pipeline = Pipeline(
            task_id=task_id,
            task=task,
            status=PipelineStatus.PENDING,
            team_preset=team_preset or "",
            target_repo=target_repo or "",
        )
        self._pipelines[task_id] = pipeline

        await self._event_bus.emit(
            OrchestratorEvent(
                type=EventType.PIPELINE_CREATED,
                task_id=task_id,
                node="orchestrator",
                data={"task": task, "team_preset": team_preset or ""},
            )
        )

        # Start pipeline execution in background
        self._bg_task = asyncio.create_task(self._execute_pipeline(pipeline))

        logger.info("pipeline_created", task_id=task_id, task=task)
        return pipeline

    async def get_pipeline(self, task_id: str) -> Pipeline | None:
        """파이프라인 ID로 파이프라인을 조회한다.

        Args:
            task_id: 파이프라인 ID.

        Returns:
            파이프라인 인스턴스. 존재하지 않으면 None.
        """
        return self._pipelines.get(task_id)

    async def list_pipelines(self) -> list[Pipeline]:
        """모든 파이프라인 목록을 반환한다.

        Returns:
            파이프라인 목록 (생성 시간 역순).
        """
        return list(reversed(self._pipelines.values()))

    async def cancel_task(self, task_id: str) -> bool:
        """실행 중인 파이프라인을 취소한다.

        Args:
            task_id: 취소할 파이프라인 ID.

        Returns:
            취소 성공 시 True. 파이프라인이 없거나 이미 완료된 경우 False.
        """
        pipeline = self._pipelines.get(task_id)
        if pipeline is None:
            return False

        cancellable = {
            PipelineStatus.PENDING,
            PipelineStatus.PLANNING,
            PipelineStatus.RUNNING,
        }
        if pipeline.status not in cancellable:
            return False

        self._pipelines[task_id] = pipeline.model_copy(update={"status": PipelineStatus.CANCELLED})

        await self._event_bus.emit(
            OrchestratorEvent(
                type=EventType.PIPELINE_CANCELLED,
                task_id=task_id,
                node="orchestrator",
                data={},
            )
        )
        logger.info("pipeline_cancelled", task_id=task_id)
        return True

    async def resume_task(self, task_id: str) -> Pipeline:
        """중단된 파이프라인을 재개한다.

        Args:
            task_id: 재개할 파이프라인 ID.

        Returns:
            재개된 파이프라인.

        Raises:
            KeyError: 파이프라인이 존재하지 않는 경우.
            ValueError: 재개할 수 없는 상태인 경우.
        """
        pipeline = self._pipelines.get(task_id)
        if pipeline is None:
            msg = f"Pipeline not found: {task_id}"
            raise KeyError(msg)

        resumable = {PipelineStatus.FAILED, PipelineStatus.PARTIAL_FAILURE}
        if pipeline.status not in resumable:
            msg = f"Pipeline {task_id} cannot be resumed from status: {pipeline.status}"
            raise ValueError(msg)

        self._pipelines[task_id] = pipeline.model_copy(update={"status": PipelineStatus.RUNNING})
        logger.info("pipeline_resumed", task_id=task_id)
        return self._pipelines[task_id]

    def list_agent_presets(self) -> list[AgentPreset]:
        """등록된 모든 에이전트 프리셋을 반환한다."""
        return self._preset_registry.list_agent_presets()

    def list_team_presets(self) -> list[TeamPreset]:
        """등록된 모든 팀 프리셋을 반환한다."""
        return self._preset_registry.list_team_presets()

    def save_agent_preset(self, preset: AgentPreset) -> None:
        """에이전트 프리셋을 저장한다."""
        self._preset_registry.save_agent_preset(preset)

    def save_team_preset(self, preset: TeamPreset) -> None:
        """팀 프리셋을 저장한다."""
        self._preset_registry.save_team_preset(preset)

    def get_board_state(self) -> dict[str, Any]:
        """칸반 보드의 현재 상태를 반환한다."""
        return self._board.get_board_state()

    def list_agents(self) -> list[dict[str, Any]]:
        """현재 활성화된 에이전트 워커 상태를 반환한다."""
        return [w.get_status() for w in self._workers.values()]

    def subscribe(
        self,
        callback: Callable[[OrchestratorEvent], Awaitable[None] | None],
    ) -> None:
        """이벤트 구독자를 등록한다.

        Args:
            callback: 이벤트 수신 콜백. sync 또는 async 함수 모두 가능.
        """
        self._event_bus.subscribe(callback)

    def get_events(
        self,
        task_id: str | None = None,
    ) -> list[OrchestratorEvent]:
        """이벤트 히스토리를 조회한다.

        Args:
            task_id: 특정 파이프라인의 이벤트만 필터링. None이면 전체.

        Returns:
            이벤트 목록 (시간순).
        """
        return self._event_bus.get_history(task_id=task_id)

    async def _execute_pipeline(self, pipeline: Pipeline) -> None:
        """파이프라인의 전체 생명주기를 실행하는 내부 코루틴.

        Phase 1에서는 상태 전이만 수행한다.
        """
        task_id = pipeline.task_id
        try:
            # PENDING -> PLANNING
            self._pipelines[task_id] = pipeline.model_copy(
                update={"status": PipelineStatus.PLANNING}
            )
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_PLANNING,
                    task_id=task_id,
                    node="orchestrator",
                    data={"subtask_count": 0},
                )
            )

            # Phase 1: stub — mark as completed without actual execution
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={"status": PipelineStatus.COMPLETED}
            )
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_COMPLETED,
                    task_id=task_id,
                    node="orchestrator",
                    data={"synthesis_length": 0, "total_duration_ms": 0},
                )
            )
        except Exception as exc:
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={
                    "status": PipelineStatus.FAILED,
                    "error": str(exc),
                }
            )
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_FAILED,
                    task_id=task_id,
                    node="orchestrator",
                    data={"error_type": type(exc).__name__, "error_message": str(exc)},
                )
            )
            logger.exception("pipeline_execution_failed", task_id=task_id)

"""OrchestratorEngine — single entry point for the Core layer."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from orchestrator.core.adapters.factory import AdapterFactory
from orchestrator.core.auth.provider import EnvAuthProvider
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.context.checkpoint import CheckpointStore
from orchestrator.core.errors.fallback import FallbackChain
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.synthesizer import Synthesizer
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.executor.cli_executor import CLIAgentExecutor
from orchestrator.core.models.pipeline import (
    FileChange,
    Pipeline,
    PipelineStatus,
    WorkerResult,
)
from orchestrator.core.models.schemas import AdapterConfig
from orchestrator.core.planner.team_planner import TeamPlanner
from orchestrator.core.presets.models import AgentPreset, TeamPreset
from orchestrator.core.presets.registry import PresetRegistry
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.models import TaskItem, TaskState
from orchestrator.core.queue.worker import AgentWorker
from orchestrator.core.utils import generate_id
from orchestrator.core.worktree.collector import FileDiffCollector
from orchestrator.core.worktree.manager import WorktreeManager

logger = structlog.get_logger()

_ORCHESTRATOR_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
_ORCHESTRATOR_PATH = Path(_ORCHESTRATOR_DIR).resolve()


class OrchestratorEngine:
    """Core 계층의 단일 진입점.

    API 계층은 이 클래스만 의존한다.
    모든 하위 컴포넌트(TaskBoard, PresetRegistry, EventBus 등)를 조합하고,
    태스크 생명주기를 관리한다.

    Hybrid 오케스트레이션 모델:
    - Planning (LangGraph/TeamPlanner): LLM 기반 태스크 분해
    - Execution (TaskBoard + AgentWorker): 기계적 분배, DAG 의존성 해소, retry
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
        self._fallback_chain = FallbackChain(event_bus=self._event_bus)
        self._synthesizer = Synthesizer(model=self.config.synthesizer_model)
        self._team_planner = TeamPlanner(
            model=self.config.planner_model,
            preset_registry=self._preset_registry,
            use_llm=self.config.planner_use_llm,
        )
        self._checkpoint_store: CheckpointStore | None = None
        if self.config.checkpoint_enabled:
            self._checkpoint_store = CheckpointStore(self.config.checkpoint_db_path)
        self._pipelines: dict[str, Pipeline] = {}
        self._workers: dict[str, AgentWorker] = {}
        self._bg_tasks: dict[str, asyncio.Task[None]] = {}

    @staticmethod
    async def _ensure_git_repo(path: str) -> None:
        """target_repo가 git 저장소가 아니면 자동 초기화."""
        import os

        os.makedirs(path, exist_ok=True)
        git_dir = os.path.join(path, ".git")
        if not os.path.isdir(git_dir):
            proc = await asyncio.create_subprocess_exec(
                "git", "init", "-b", "main", cwd=path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            for cmd in [
                ["git", "config", "user.name", "orchestrator"],
                ["git", "config", "user.email", "orch@localhost"],
            ]:
                p = await asyncio.create_subprocess_exec(
                    *cmd, cwd=path,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await p.wait()
            # 빈 초기 커밋
            gitkeep = os.path.join(path, ".gitkeep")
            if not os.path.exists(gitkeep):
                with open(gitkeep, "w") as f:
                    f.write("")
            for cmd in [
                ["git", "add", "-A"],
                ["git", "commit", "-m", "init: orchestrator target repo"],
            ]:
                p = await asyncio.create_subprocess_exec(
                    *cmd, cwd=path,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await p.wait()
            logger.info("target_repo_initialized", path=path)

    @staticmethod
    def _is_protected_target_repo(path: str) -> bool:
        """target_repo가 오케스트레이터 저장소 자신인지 확인한다."""
        candidate_path = Path(path).expanduser().resolve(strict=False)

        try:
            return os.path.commonpath(
                [str(candidate_path), str(_ORCHESTRATOR_PATH)]
            ) == str(_ORCHESTRATOR_PATH)
        except ValueError:
            return False

    async def start(self) -> None:
        """엔진을 시작한다. 리소스 초기화."""
        logger.info("engine_starting")

    async def shutdown(self) -> None:
        """엔진을 종료한다. 워커 정지, 리소스 해제."""
        logger.info("engine_shutting_down")
        # Stop all active workers
        for wid, worker in list(self._workers.items()):
            try:
                await worker.stop()
            except Exception:
                logger.warning("worker_stop_failed_on_shutdown", worker_id=wid)
        self._workers.clear()
        # Cancel background tasks
        for _tid, bg_task in list(self._bg_tasks.items()):
            bg_task.cancel()
        self._bg_tasks.clear()
        logger.info("engine_shutdown_complete")

    @property
    def event_bus(self) -> EventBus:
        """이벤트 버스를 반환한다."""
        return self._event_bus

    @property
    def checkpoint_store(self) -> CheckpointStore | None:
        """체크포인트 저장소를 반환한다."""
        return self._checkpoint_store

    def _save_checkpoint(self, pipeline: Pipeline) -> None:
        """파이프라인 상태를 체크포인트에 저장한다.

        Args:
            pipeline: 저장할 파이프라인.
        """
        if self._checkpoint_store is not None:
            self._checkpoint_store.save(pipeline.task_id, pipeline)

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

        # cwd 자기 보호: 오케스트레이터 저장소 및 하위 경로에서 CLI 실행 방지
        if target_repo and self._is_protected_target_repo(target_repo):
            raise ValueError(
                f"CLI cannot run in orchestrator directory: {target_repo}"
            )

        # target_repo가 git repo가 아니면 자동 초기화
        if target_repo:
            await self._ensure_git_repo(target_repo)

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
        bg = asyncio.create_task(self._execute_pipeline(pipeline))
        self._bg_tasks[task_id] = bg

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
        """중단된 파이프라인을 재개한다 (체크포인트 기반).

        1. 메모리에서 파이프라인을 찾고, 없으면 체크포인트에서 복원.
        2. 실패/부분 실패 상태인지 확인.
        3. TaskBoard의 failed 태스크를 todo로 리셋.
        4. 파이프라인 상태를 RUNNING으로 전이.

        Args:
            task_id: 재개할 파이프라인 ID.

        Returns:
            재개된 파이프라인.

        Raises:
            KeyError: 파이프라인이 존재하지 않는 경우.
            ValueError: 재개할 수 없는 상태인 경우.
        """
        pipeline = self._pipelines.get(task_id)

        # 메모리에 없으면 체크포인트에서 복원 시도
        if pipeline is None and self._checkpoint_store is not None:
            pipeline = self._checkpoint_store.load(task_id)
            if pipeline is not None:
                self._pipelines[task_id] = pipeline

        if pipeline is None:
            msg = f"Pipeline not found: {task_id}"
            raise KeyError(msg)

        resumable = {PipelineStatus.FAILED, PipelineStatus.PARTIAL_FAILURE}
        if pipeline.status not in resumable:
            msg = f"Pipeline {task_id} cannot be resumed from status: {pipeline.status}"
            raise ValueError(msg)

        # TaskBoard의 failed 태스크를 todo로 리셋
        for task_item in self._board._tasks.values():
            if task_item.pipeline_id == task_id and task_item.state == TaskState.FAILED:
                self._board._tasks[task_item.id] = task_item.model_copy(
                    update={
                        "state": TaskState.TODO,
                        "error": "",
                        "assigned_to": None,
                    }
                )

        self._pipelines[task_id] = pipeline.model_copy(
            update={"status": PipelineStatus.RUNNING, "error": ""}
        )
        self._save_checkpoint(self._pipelines[task_id])

        await self._event_bus.emit(
            OrchestratorEvent(
                type=EventType.PIPELINE_RUNNING,
                task_id=task_id,
                node="orchestrator",
                data={"resumed": True},
            )
        )

        logger.info("pipeline_resumed", task_id=task_id)
        return self._pipelines[task_id]

    def list_agent_presets(self) -> list[AgentPreset]:
        """등록된 모든 에이전트 프리셋을 반환한다."""
        return self._preset_registry.list_agent_presets()

    def list_team_presets(self) -> list[TeamPreset]:
        """등록된 모든 팀 프리셋을 반환한다."""
        return self._preset_registry.list_team_presets()

    def load_agent_preset(self, name: str) -> AgentPreset:
        """이름으로 에이전트 프리셋을 조회한다.

        Args:
            name: 프리셋 이름.

        Returns:
            프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        return self._preset_registry.load_agent_preset(name)

    def load_team_preset(self, name: str) -> TeamPreset:
        """이름으로 팀 프리셋을 조회한다.

        Args:
            name: 팀 프리셋 이름.

        Returns:
            팀 프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        return self._preset_registry.load_team_preset(name)

    def save_agent_preset(
        self,
        preset: AgentPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """에이전트 프리셋을 저장한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        self._preset_registry.save_agent_preset(preset, overwrite=overwrite)

    def save_team_preset(
        self,
        preset: TeamPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """팀 프리셋을 저장한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        self._preset_registry.save_team_preset(preset, overwrite=overwrite)

    def get_board_state(self) -> dict[str, Any]:
        """칸반 보드의 현재 상태를 반환한다."""
        return self._board.get_board_state()

    def get_board_task(self, task_id: str) -> TaskItem | None:
        """보드에서 특정 태스크를 조회한다.

        Args:
            task_id: 태스크 ID.

        Returns:
            TaskItem 또는 None.
        """
        return self._board.get_task(task_id)

    async def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        """파이프라인의 아티팩트 목록을 반환한다.

        Args:
            task_id: 파이프라인 ID.

        Returns:
            아티팩트 메타데이터 목록.
        """
        pipeline = self._pipelines.get(task_id)
        if pipeline is None:
            return []
        artifacts: list[dict[str, Any]] = []
        # Results as artifacts
        for wr in pipeline.results:
            if wr.output:
                artifacts.append(
                    {
                        "path": f"subtask-{wr.subtask_id}/output.json",
                        "type": "agent_output",
                        "size_bytes": len(wr.output.encode("utf-8")),
                        "agent": None,
                        "subtask_id": wr.subtask_id,
                        "created_at": pipeline.completed_at.isoformat()
                        if pipeline.completed_at
                        else None,
                    }
                )
        # Synthesis as artifact
        if pipeline.synthesis:
            artifacts.append(
                {
                    "path": "synthesis/final-report.md",
                    "type": "synthesis",
                    "size_bytes": len(pipeline.synthesis.encode("utf-8")),
                    "agent": None,
                    "subtask_id": None,
                    "created_at": pipeline.completed_at.isoformat()
                    if pipeline.completed_at
                    else None,
                }
            )
        return artifacts

    async def get_artifact(self, task_id: str, path: str) -> str | None:
        """아티팩트 파일 내용을 반환한다.

        Args:
            task_id: 파이프라인 ID.
            path: 아티팩트 상대 경로.

        Returns:
            파일 내용 또는 None.
        """
        pipeline = self._pipelines.get(task_id)
        if pipeline is None:
            return None
        if path == "synthesis/final-report.md" and pipeline.synthesis:
            return pipeline.synthesis
        # Check subtask outputs
        for wr in pipeline.results:
            if path == f"subtask-{wr.subtask_id}/output.json" and wr.output:
                return wr.output
        return None

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

    def _create_executor_for_preset(
        self,
        preset_name: str,
        *,
        cwd: str | None = None,
    ) -> AgentExecutor:
        """에이전트 프리셋에 맞는 AgentExecutor를 생성한다.

        Args:
            preset_name: AgentPreset 이름.
            cwd: CLI 실행 디렉토리 (worktree 경로).

        Returns:
            AgentExecutor 인스턴스.
        """
        try:
            preset = self._preset_registry.load_agent_preset(preset_name)
        except KeyError:
            # 프리셋이 없으면 기본 설정 사용
            logger.warning("preset_not_found_using_default", preset_name=preset_name)
            preset = None

        if preset is not None and preset.preferred_cli is not None:
            cli_name = preset.preferred_cli or "claude"
            adapter = self._adapter_factory.create(cli_name)
            config = AdapterConfig(
                timeout=preset.limits.timeout,
                working_dir=cwd,
            )
            persona = preset.persona.to_system_prompt()
            executor = CLIAgentExecutor(
                adapter=adapter,
                config=config,
                persona_prompt=persona,
            )
            executor.cli_name = cli_name  # type: ignore[attr-defined]
            return executor

        # Default: mock-compatible executor path
        # When no preset or unsupported mode, use the first available CLI
        adapter = self._adapter_factory.create("claude")
        config = AdapterConfig(timeout=300, working_dir=cwd)
        executor = CLIAgentExecutor(adapter=adapter, config=config)
        executor.cli_name = "claude"  # type: ignore[attr-defined]
        return executor

    async def _execute_pipeline(self, pipeline: Pipeline) -> None:
        """파이프라인의 전체 생명주기를 실행하는 내부 코루틴.

        Hybrid 오케스트레이션 흐름:
        1. PENDING -> PLANNING: TeamPlanner로 태스크 분해
        2. PLANNING -> RUNNING: TaskBoard에 서브태스크 투입, AgentWorker 시작
        3. RUNNING: AgentWorker가 태스크 소비 및 실행
        4. RUNNING -> SYNTHESIZING: 모든 태스크 완료 후 Synthesizer로 종합
        5. SYNTHESIZING -> COMPLETED: 종합 보고서 생성 완료
        """
        task_id = pipeline.task_id
        pipeline_workers: list[str] = []
        worktree_branches: list[str] = []
        pipeline_start = time.monotonic()

        try:
            # ── Phase 1: PENDING → PLANNING ──────────────────────────────
            decomposition_start = time.monotonic()
            self._pipelines[task_id] = pipeline.model_copy(
                update={
                    "status": PipelineStatus.PLANNING,
                    "started_at": datetime.utcnow(),
                }
            )
            self._save_checkpoint(self._pipelines[task_id])
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_PLANNING,
                    task_id=task_id,
                    node="orchestrator",
                    data={},
                )
            )

            # TeamPlanner 사용: 태스크 → 서브태스크 분해
            team_preset_obj: TeamPreset | None = None
            if pipeline.team_preset:
                team_preset_obj = self._preset_registry.load_team_preset(pipeline.team_preset)

            subtasks, used_preset = await self._team_planner.plan_team(
                pipeline.task,
                team_preset=team_preset_obj,
                target_repo=pipeline.target_repo or None,
            )
            decomposition_ms = int((time.monotonic() - decomposition_start) * 1000)
            logger.info(
                "perf_decomposition",
                task_id=task_id,
                decomposition_ms=decomposition_ms,
                subtask_count=len(subtasks),
            )

            # Pipeline에 서브태스크 기록
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={"subtasks": subtasks}
            )
            self._save_checkpoint(self._pipelines[task_id])

            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_PLANNING,
                    task_id=task_id,
                    node="orchestrator",
                    data={"subtask_count": len(subtasks)},
                )
            )

            # ── Phase 2: PLANNING → RUNNING ──────────────────────────────
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={"status": PipelineStatus.RUNNING}
            )
            self._save_checkpoint(self._pipelines[task_id])
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_RUNNING,
                    task_id=task_id,
                    node="orchestrator",
                    data={"subtask_count": len(subtasks)},
                )
            )

            # Worktree 설정 (target_repo가 있는 경우)
            worktree_paths: dict[str, str] = {}  # lane -> worktree path
            worktree_paths_by_branch: dict[str, str] = {}  # branch -> worktree path
            if pipeline.target_repo:
                for st in subtasks:
                    lane = st.assigned_preset or "default"
                    if lane not in worktree_paths:
                        branch_name = f"orch-{task_id.replace('pipeline-', '')[:8]}-{lane}"
                        try:
                            wt_path = await self._worktree_manager.create(
                                pipeline.target_repo,
                                branch_name,
                            )
                            worktree_paths[lane] = str(wt_path)
                            worktree_paths_by_branch[branch_name] = str(wt_path)
                            worktree_branches.append(branch_name)
                            await self._event_bus.emit(
                                OrchestratorEvent(
                                    type=EventType.WORKTREE_CREATED,
                                    task_id=task_id,
                                    node="orchestrator",
                                    data={
                                        "branch": branch_name,
                                        "path": str(wt_path),
                                    },
                                )
                            )
                        except Exception as wt_err:
                            logger.warning(
                                "worktree_create_failed",
                                task_id=task_id,
                                lane=lane,
                                error=str(wt_err),
                            )

            # 서브태스크 → TaskItem 변환 + TaskBoard 투입
            for st in subtasks:
                lane = st.assigned_preset or "default"
                task_item = TaskItem(
                    id=st.id,
                    title=st.description[:200],
                    description=st.description,
                    lane=lane,
                    depends_on=st.depends_on,
                    pipeline_id=task_id,
                    priority=st.priority,
                    max_retries=self.config.default_max_retries,
                )
                await self._board.submit(task_item)
                await self._event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.TASK_SUBMITTED,
                        task_id=task_id,
                        node="orchestrator",
                        data={
                            "subtask_id": st.id,
                            "lane": lane,
                            "description": st.description[:200],
                        },
                    )
                )

            # AgentWorker 생성 및 시작 (레인별 1개)
            lanes_needed: set[str] = {st.assigned_preset or "default" for st in subtasks}
            for lane in lanes_needed:
                worker_id = f"worker-{task_id[:8]}-{lane}"
                cwd = worktree_paths.get(lane)
                executor = self._create_executor_for_preset(lane, cwd=cwd)

                worker = AgentWorker(
                    worker_id=worker_id,
                    lane=lane,
                    board=self._board,
                    executor=executor,
                    event_bus=self._event_bus,
                    poll_interval=0.2,
                    show_output=self.config.show_cli_output,
                )
                self._workers[worker_id] = worker
                pipeline_workers.append(worker_id)
                await worker.start()

            # ── Phase 3: RUNNING — 모든 태스크 완료 대기 ─────────────────
            execution_start = time.monotonic()
            while not self._board.is_all_done(task_id):
                # 취소 확인
                current = self._pipelines.get(task_id)
                if current and current.status == PipelineStatus.CANCELLED:
                    return
                await asyncio.sleep(0.1)
            execution_ms = int((time.monotonic() - execution_start) * 1000)
            logger.info(
                "perf_execution",
                task_id=task_id,
                execution_ms=execution_ms,
            )

            # Per-subtask duration logging
            for st in subtasks:
                finished_item = self._board.get_task(st.id)
                if (
                    finished_item is not None
                    and finished_item.started_at is not None
                    and finished_item.completed_at is not None
                ):
                    subtask_ms = int(
                        (finished_item.completed_at - finished_item.started_at).total_seconds()
                        * 1000
                    )
                    logger.info(
                        "perf_subtask",
                        task_id=task_id,
                        subtask_id=st.id,
                        subtask_ms=subtask_ms,
                        lane=finished_item.lane,
                        state=finished_item.state.value,
                    )

            # ── Phase 3.5: Quality Gate — reviewer 결과 평가 + 재작업 ────
            if self.config.quality_gate_enabled:
                from orchestrator.core.quality_gate import QualityGate

                quality_gate = QualityGate(
                    verdict_format=self.config.quality_gate_verdict_format,
                )
                max_review_iterations = self.config.max_review_iterations
            else:
                max_review_iterations = 0

            review_iteration = 0

            while review_iteration < max_review_iterations:
                # reviewer subtask 찾기
                reviewer_tasks = [
                    self._board.get_task(st.id)
                    for st in subtasks
                    if (st.assigned_preset or "").lower() in ("reviewer", "auditor")
                ]
                reviewer_tasks = [t for t in reviewer_tasks if t and t.result]

                needs_rework = False
                for rt in reviewer_tasks:
                    verdict = quality_gate.evaluate(rt.result, "reviewer")
                    if not verdict.approved:
                        logger.info(
                            "quality_gate_rework_needed",
                            task_id=task_id,
                            reviewer_task=rt.id,
                            iteration=review_iteration + 1,
                        )
                        # implementer 재작업 태스크 생성
                        rework_id = generate_id("rework")
                        rework_task = TaskItem(
                            id=rework_id,
                            title=f"재작업 (iteration {review_iteration + 1})",
                            description=(
                                f"리뷰어 피드백에 따라 코드를 수정하세요:\n\n"
                                f"{verdict.feedback[:2000]}\n\n"
                                f"사용자 태스크: {pipeline.task}"
                            ),
                            lane="implementer",
                            depends_on=[],
                            pipeline_id=task_id,
                        )
                        await self._board.submit(rework_task)

                        # 재리뷰 태스크
                        re_review_id = generate_id("review")
                        re_review_task = TaskItem(
                            id=re_review_id,
                            title=f"재리뷰 (iteration {review_iteration + 1})",
                            description=(
                            f"재작업된 코드를 리뷰하세요.\n\n"
                            f"사용자 태스크: {pipeline.task}"
                        ),
                            lane="reviewer",
                            depends_on=[rework_id],
                            pipeline_id=task_id,
                        )
                        await self._board.submit(re_review_task)

                        needs_rework = True
                        break

                if not needs_rework:
                    break

                # 재작업 완료 대기
                while not self._board.is_all_done(task_id):
                    current = self._pipelines.get(task_id)
                    if current and current.status == PipelineStatus.CANCELLED:
                        return
                    await asyncio.sleep(0.1)

                review_iteration += 1

            # ── Phase 4: RUNNING → SYNTHESIZING ──────────────────────────
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={"status": PipelineStatus.SYNTHESIZING}
            )
            self._save_checkpoint(self._pipelines[task_id])
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_SYNTHESIZING,
                    task_id=task_id,
                    node="orchestrator",
                    data={},
                )
            )

            # 워커 정지
            await self._stop_pipeline_workers(pipeline_workers)

            # FileDiff 수집 (worktree가 있는 경우)
            file_changes_map: dict[str, list[FileChange]] = {}
            for lane_name, wt_dir in worktree_paths.items():
                collector = FileDiffCollector(wt_dir)
                try:
                    changes = await collector.collect_changes()
                    file_changes_map[lane_name] = changes
                except Exception:
                    logger.warning("diff_collect_failed", lane=lane_name, path=wt_dir)

            # Commit + merge worktree changes to target_repo
            if pipeline.target_repo and worktree_branches:
                for branch in worktree_branches:
                    branch_wt_path = worktree_paths_by_branch.get(branch)
                    if branch_wt_path:
                        committed = await self._commit_worktree_changes(
                            branch_wt_path, f"agent: {branch}"
                        )
                        if committed:
                            logger.info(
                                "worktree_committed",
                                branch=branch,
                                path=branch_wt_path,
                            )

                if self.config.auto_merge:
                    for branch in worktree_branches:
                        try:
                            merged = await self._worktree_manager.merge_to_target(
                                branch, strategy=self.config.merge_strategy,
                            )
                            if merged:
                                logger.info("worktree_merged", branch=branch)
                                await self._event_bus.emit(
                                    OrchestratorEvent(
                                        type=EventType.WORKTREE_MERGED,
                                        task_id=task_id,
                                        node="orchestrator",
                                        data={"branch": branch},
                                    )
                                )
                            else:
                                logger.warning("worktree_merge_failed", branch=branch)
                                self._pipelines[task_id] = self._pipelines[
                                    task_id
                                ].model_copy(
                                    update={
                                        "error": (
                                            self._pipelines[task_id].error
                                            + f"merge conflict: {branch}; "
                                        )
                                    }
                                )
                        except Exception as merge_err:
                            logger.warning(
                                "worktree_merge_failed",
                                branch=branch,
                                error=str(merge_err),
                            )
                            self._pipelines[task_id] = self._pipelines[
                                task_id
                            ].model_copy(
                                update={
                                    "error": (
                                        self._pipelines[task_id].error
                                        + f"merge conflict: {branch}; "
                                    )
                                }
                            )
                else:
                    logger.info(
                        "auto_merge_disabled",
                        task_id=task_id,
                        branches=worktree_branches,
                    )

            # 결과 수집: TaskBoard의 DONE 태스크 → WorkerResult
            done_tasks = self._board.get_results(task_id)
            worker_results: list[WorkerResult] = []
            for dt in done_tasks:
                lane = dt.lane
                wr = WorkerResult(
                    subtask_id=dt.id,
                    executor_type="cli",
                    output=dt.result,
                    files_changed=file_changes_map.get(lane, []),
                )
                worker_results.append(wr)

            # 실패한 태스크도 WorkerResult로 기록
            all_pipeline_tasks = [
                t for t in self._board._tasks.values() if t.pipeline_id == task_id
            ]
            failed_tasks = [t for t in all_pipeline_tasks if t.state.value == "failed"]
            for ft in failed_tasks:
                wr = WorkerResult(
                    subtask_id=ft.id,
                    executor_type="cli",
                    output="",
                    error=ft.error,
                )
                worker_results.append(wr)

            # 부분 실패 확인
            total_count = len(all_pipeline_tasks)
            fail_count = len(failed_tasks)
            success_count = len(done_tasks)
            fail_ratio = fail_count / total_count if total_count > 0 else 0.0

            if fail_count > 0 and success_count == 0:
                # 100% 실패 → FAILED
                self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                    update={
                        "status": PipelineStatus.FAILED,
                        "results": worker_results,
                        "error": f"All {fail_count} subtasks failed",
                        "completed_at": datetime.utcnow(),
                    }
                )
                self._save_checkpoint(self._pipelines[task_id])
                await self._event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.PIPELINE_FAILED,
                        task_id=task_id,
                        node="orchestrator",
                        data={
                            "error_message": f"All {fail_count} subtasks failed",
                            "fail_count": fail_count,
                            "total_count": total_count,
                        },
                    )
                )
                return

            if fail_ratio >= 0.5:
                # 50% 이상 실패 → FAILED (결과는 보존)
                self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                    update={
                        "status": PipelineStatus.FAILED,
                        "results": worker_results,
                        "error": f"{fail_count}/{total_count} subtasks failed (>= 50%)",
                        "completed_at": datetime.utcnow(),
                    }
                )
                self._save_checkpoint(self._pipelines[task_id])
                await self._event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.PIPELINE_FAILED,
                        task_id=task_id,
                        node="orchestrator",
                        data={
                            "error_message": f"{fail_count}/{total_count} subtasks failed",
                            "fail_count": fail_count,
                            "total_count": total_count,
                            "fail_ratio": fail_ratio,
                        },
                    )
                )
                return

            # <50% 실패 또는 0% 실패 → 종합 진행
            # synthesis.started 이벤트
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.SYNTHESIS_STARTED,
                    task_id=task_id,
                    node="orchestrator",
                    data={
                        "strategy": used_preset.synthesis_strategy,
                        "input_count": len(worker_results),
                    },
                )
            )

            # Synthesizer로 종합 보고서 생성 (실패 정보 포함)
            synthesis_start = time.monotonic()
            synthesis = await self._synthesizer.synthesize(
                worker_results,
                pipeline.task,
                strategy=used_preset.synthesis_strategy,
            )
            synthesis_ms = int((time.monotonic() - synthesis_start) * 1000)
            logger.info(
                "perf_synthesis",
                task_id=task_id,
                synthesis_ms=synthesis_ms,
                report_length=len(synthesis),
            )

            # synthesis.completed 이벤트
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.SYNTHESIS_COMPLETED,
                    task_id=task_id,
                    node="orchestrator",
                    data={
                        "result_preview": synthesis[:200],
                        "synthesis_ms": synthesis_ms,
                    },
                )
            )

            # merged flag — set by earlier commit+merge block
            merged = bool(pipeline.target_repo and worktree_branches)

            # ── Phase 5: SYNTHESIZING → COMPLETED / PARTIAL_FAILURE ─────
            final_status = (
                PipelineStatus.PARTIAL_FAILURE if fail_count > 0 else PipelineStatus.COMPLETED
            )
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={
                    "status": final_status,
                    "results": worker_results,
                    "synthesis": synthesis,
                    "merged": merged,
                    "completed_at": datetime.utcnow(),
                }
            )
            self._save_checkpoint(self._pipelines[task_id])
            total_pipeline_ms = int((time.monotonic() - pipeline_start) * 1000)
            logger.info(
                "perf_pipeline_total",
                task_id=task_id,
                total_pipeline_ms=total_pipeline_ms,
                decomposition_ms=decomposition_ms,
                execution_ms=execution_ms,
                synthesis_ms=synthesis_ms,
                subtask_count=len(subtasks),
                success_count=success_count,
                fail_count=fail_count,
            )
            event_type = EventType.PIPELINE_COMPLETED
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=event_type,
                    task_id=task_id,
                    node="orchestrator",
                    data={
                        "synthesis_length": len(synthesis),
                        "total_duration_ms": total_pipeline_ms,
                        "status": final_status,
                        "fail_count": fail_count,
                        "success_count": success_count,
                    },
                )
            )

        except Exception as exc:
            self._pipelines[task_id] = self._pipelines[task_id].model_copy(
                update={
                    "status": PipelineStatus.FAILED,
                    "error": str(exc),
                    "completed_at": datetime.utcnow(),
                }
            )
            self._save_checkpoint(self._pipelines[task_id])
            await self._event_bus.emit(
                OrchestratorEvent(
                    type=EventType.PIPELINE_FAILED,
                    task_id=task_id,
                    node="orchestrator",
                    data={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
            )
            logger.exception("pipeline_execution_failed", task_id=task_id)
        finally:
            # Cleanup: 워커 정지, worktree 정리
            await self._stop_pipeline_workers(pipeline_workers)
            if pipeline.target_repo and self.config.worktree_cleanup:
                for branch in worktree_branches:
                    try:
                        await self._worktree_manager.cleanup(
                            branch,
                        )
                    except Exception:
                        logger.warning(
                            "worktree_cleanup_failed",
                            branch=branch,
                        )
            elif pipeline.target_repo and not self.config.worktree_cleanup:
                logger.info(
                    "worktree_cleanup_skipped",
                    task_id=task_id,
                    branches=worktree_branches,
                )
            # Background task 정리
            self._bg_tasks.pop(task_id, None)

    async def _commit_worktree_changes(self, worktree_path: str, message: str) -> bool:
        """Commit any uncommitted changes in a worktree directory.

        Args:
            worktree_path: worktree 디렉토리 경로.
            message: 커밋 메시지.

        Returns:
            변경사항이 있어 커밋되었으면 True, 변경사항 없으면 False.
        """
        if not os.path.isdir(worktree_path):
            logger.warning("worktree_commit_skip_no_dir", path=worktree_path)
            return False

        # git add -A
        proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A", cwd=worktree_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0:
            return False

        # Check if there are changes to commit
        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "--cached", "--quiet", cwd=worktree_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode == 0:
            return False  # no changes

        # git commit
        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", message, cwd=worktree_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def _stop_pipeline_workers(
        self,
        worker_ids: list[str],
    ) -> None:
        """파이프라인에 속한 워커들을 정지한다.

        Args:
            worker_ids: 정지할 워커 ID 목록.
        """
        for wid in worker_ids:
            worker = self._workers.get(wid)
            if worker is not None:
                try:
                    await worker.stop()
                except Exception:
                    logger.warning("worker_stop_failed", worker_id=wid)
                finally:
                    self._workers.pop(wid, None)

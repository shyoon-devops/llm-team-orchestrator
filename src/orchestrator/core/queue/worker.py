"""AgentWorker — lane-based task consumer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.queue.models import TaskState

if TYPE_CHECKING:
    from orchestrator.core.events.bus import EventBus
    from orchestrator.core.executor.base import AgentExecutor
    from orchestrator.core.queue.board import TaskBoard

logger = structlog.get_logger()


class AgentWorker:
    """특정 레인을 담당하는 워커.

    폴링 루프로 TaskBoard에서 태스크를 소비하고 에이전트를 실행한다.
    """

    def __init__(
        self,
        worker_id: str,
        lane: str,
        board: TaskBoard,
        executor: AgentExecutor,
        event_bus: EventBus,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        """
        Args:
            worker_id: 워커 고유 ID.
            lane: 담당 레인 이름.
            board: 태스크 보드 참조.
            executor: 에이전트 실행기.
            event_bus: 이벤트 발행기.
            poll_interval: 태스크 폴링 간격 (초).
        """
        self.worker_id = worker_id
        self.lane = lane
        self.board = board
        self.executor = executor
        self.event_bus = event_bus
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._tasks_completed = 0
        self._current_task_id: str | None = None

    async def start(self) -> None:
        """워커를 시작한다. 백그라운드 폴링 루프를 생성한다.

        Raises:
            RuntimeError: 이미 실행 중인 경우.
        """
        if self._running:
            msg = f"Worker {self.worker_id} is already running"
            raise RuntimeError(msg)
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        await self.event_bus.emit(
            OrchestratorEvent(
                type=EventType.WORKER_STARTED,
                node=self.worker_id,
                data={"worker_id": self.worker_id, "lane": self.lane},
            )
        )
        logger.info("worker_started", worker_id=self.worker_id, lane=self.lane)

    async def stop(self) -> None:
        """워커를 정지한다.

        현재 실행 중인 태스크가 있으면 완료를 기다린다.
        """
        import contextlib

        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.event_bus.emit(
            OrchestratorEvent(
                type=EventType.WORKER_STOPPED,
                node=self.worker_id,
                data={"worker_id": self.worker_id, "lane": self.lane},
            )
        )
        logger.info("worker_stopped", worker_id=self.worker_id, lane=self.lane)

    async def _run_loop(self) -> None:
        """워커의 메인 폴링 루프. 태스크를 claim하고 실행한다."""
        while self._running:
            task = await self.board.claim(self.lane, self.worker_id)
            if task is None:
                await asyncio.sleep(self.poll_interval)
                continue

            self._current_task_id = task.id
            await self.event_bus.emit(
                OrchestratorEvent(
                    type=EventType.AGENT_EXECUTING,
                    task_id=task.pipeline_id,
                    node=self.worker_id,
                    data={
                        "task_id": task.id,
                        "cli": getattr(self.executor, "cli_name", "unknown"),
                        "prompt_length": len(task.description),
                    },
                )
            )

            try:
                result = await self.executor.run(
                    task.description,
                    timeout=300,
                    context=None,
                )
                await self.board.complete(task.id, result.output)
                self._tasks_completed += 1
                await self.event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.TASK_COMPLETED,
                        task_id=task.pipeline_id,
                        node=self.worker_id,
                        data={
                            "subtask_id": task.id,
                            "duration_ms": result.duration_ms,
                            "tokens_used": result.tokens_used,
                        },
                    )
                )
            except Exception as exc:
                error_msg = str(exc)
                await self.board.fail(task.id, error_msg)

                # Check if it was retried or failed permanently
                updated_task = self.board.get_task(task.id)
                if updated_task and updated_task.state == TaskState.TODO:
                    event_type = EventType.TASK_RETRYING
                    event_data: dict[str, Any] = {
                        "subtask_id": task.id,
                        "retry_count": updated_task.retry_count,
                        "max_retries": updated_task.max_retries,
                    }
                else:
                    event_type = EventType.TASK_FAILED
                    event_data = {
                        "subtask_id": task.id,
                        "error": error_msg,
                    }

                await self.event_bus.emit(
                    OrchestratorEvent(
                        type=event_type,
                        task_id=task.pipeline_id,
                        node=self.worker_id,
                        data=event_data,
                    )
                )
            finally:
                self._current_task_id = None

    def get_status(self) -> dict[str, Any]:
        """워커 상태를 반환한다.

        Returns:
            워커 상태 딕셔너리.
        """
        if not self._running:
            status = "stopped"
        elif self._current_task_id:
            status = "busy"
        else:
            status = "idle"

        return {
            "worker_id": self.worker_id,
            "lane": self.lane,
            "status": status,
            "current_task": self._current_task_id,
            "tasks_completed": self._tasks_completed,
        }

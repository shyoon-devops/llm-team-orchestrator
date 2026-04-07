"""AgentWorker — lane-based task consumer."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Any

import structlog

from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.queue.models import TaskState

if TYPE_CHECKING:
    from orchestrator.core.events.bus import EventBus
    from orchestrator.core.executor.base import AgentExecutor
    from orchestrator.core.queue.board import TaskBoard

logger = structlog.get_logger()

_HEARTBEAT_INTERVAL_S = 10.0


class AgentWorker:
    """특정 레인을 담당하는 워커.

    폴링 루프로 TaskBoard에서 태스크를 소비하고 에이전트를 실행한다.
    실행 중 10초 간격으로 WORKER_HEARTBEAT 이벤트를 발행한다.
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
        show_output: bool = False,
        stream_output: bool = True,
    ) -> None:
        """
        Args:
            worker_id: 워커 고유 ID.
            lane: 담당 레인 이름.
            board: 태스크 보드 참조.
            executor: 에이전트 실행기.
            event_bus: 이벤트 발행기.
            poll_interval: 태스크 폴링 간격 (초).
            show_output: CLI stdout 실시간 표시 여부.
            stream_output: CLI 출력을 AGENT_OUTPUT 이벤트로 스트리밍 여부.
        """
        self.worker_id = worker_id
        self.lane = lane
        self.board = board
        self.executor = executor
        self.event_bus = event_bus
        self.poll_interval = poll_interval
        self._show_output = show_output
        self._stream_output = stream_output
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._tasks_completed = 0
        self._current_task_id: str | None = None
        self._start_time: float = 0.0

    async def start(self) -> None:
        """워커를 시작한다. 백그라운드 폴링 루프를 생성한다.

        Raises:
            RuntimeError: 이미 실행 중인 경우.
        """
        if self._running:
            msg = f"Worker {self.worker_id} is already running"
            raise RuntimeError(msg)
        self._running = True
        self._start_time = time.monotonic()
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
        """워커의 메인 폴링 루프. 태스크를 claim하고 실행한다.

        executor.run()과 heartbeat 루프를 동시에 실행한다.
        """
        while self._running:
            task = await self.board.claim(self.lane, self.worker_id)
            if task is None:
                # Emit heartbeat while idle (periodic check)
                await self._emit_heartbeat()
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
                # Run executor and heartbeat concurrently
                result = await self._run_with_heartbeat(task)

                # show_cli_output: 실행 결과를 콘솔에 표시
                if self._show_output and result.output:
                    logger.info(
                        "cli_output",
                        worker_id=self.worker_id,
                        task_id=task.id,
                        output=result.output[:2000],
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

    async def _build_prompt(self, task: Any) -> str:
        """선행 태스크 결과를 포함한 프롬프트 구성.

        depends_on에 지정된 선행 태스크의 결과를 수집하여
        현재 태스크의 프롬프트에 컨텍스트로 주입한다.

        Args:
            task: 실행할 TaskItem.

        Returns:
            컨텍스트가 포함된 프롬프트 문자열.
        """
        prompt: str = task.description
        if task.depends_on:
            context_parts = ["\n\n--- 이전 단계 결과 ---"]
            for dep_id in task.depends_on:
                dep_task = self.board.get_task(dep_id)
                if dep_task and dep_task.result:
                    context_parts.append(
                        f"\n[{dep_task.lane}] {dep_task.result[:3000]}"
                    )
            prompt += "\n".join(context_parts)
            logger.info(
                "context_chaining",
                task_id=task.id,
                lane=task.lane,
                depends_on=task.depends_on,
                context_length=len(prompt) - len(task.description),
            )
        # cwd가 있으면 작업 디렉토리 안내 추가
        cwd = getattr(self.executor, '_cwd', None)
        if not cwd:
            config = getattr(self.executor, 'config', None)
            if config:
                cwd = getattr(config, 'working_dir', None)
        if cwd:
            prompt += (
                f"\n\n작업 디렉토리: {cwd}\n"
                f"반드시 이 디렉토리에 실제 파일을 생성하세요.\n"
                f"예시: src/main.py, tests/test_main.py 등\n"
                f"stdout으로 코드를 출력하지 말고 파일로 저장하세요.\n"
                f"파일을 생성한 뒤 어떤 파일을 만들었는지 알려주세요."
            )

        return prompt

    async def _run_with_heartbeat(self, task: Any) -> Any:
        """Run executor.run() with concurrent heartbeat emission.

        During long-running executor.run() calls, emit WORKER_HEARTBEAT
        every 10 seconds with elapsed_ms and timeout_ms.
        CLI 출력을 라인 단위로 AGENT_OUTPUT 이벤트로 스트리밍한다.
        """
        from orchestrator.core.models.schemas import AgentResult

        enriched_prompt = await self._build_prompt(task)

        # 스트리밍 콜백 주입
        async def _on_cli_output(line: str, stream: str) -> None:
            if not line.strip():
                return  # 빈 라인 무시
            await self.event_bus.emit(
                OrchestratorEvent(
                    type=EventType.AGENT_OUTPUT,
                    task_id=task.pipeline_id,
                    node=self.worker_id,
                    data={
                        "subtask_id": task.id,
                        "line": line[:2000],
                        "stream": stream,
                        "lane": self.lane,
                    },
                )
            )

        if self._stream_output and hasattr(self.executor, "_on_output"):
            self.executor._on_output = _on_cli_output

        # 프리셋의 timeout 사용 (executor.config에 설정됨), 없으면 300s 기본값
        exec_timeout = 300
        if hasattr(self.executor, "config") and self.executor.config:
            exec_timeout = getattr(self.executor.config, "timeout", 300)

        exec_task = asyncio.create_task(
            self.executor.run(
                enriched_prompt,
                timeout=exec_timeout,
                context=None,
            )
        )

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task.pipeline_id, task.id))

        try:
            result: AgentResult = await exec_task

            # CLI stdout에서 코드 블록 추출 → 파일 저장
            cwd = getattr(self.executor, '_cwd', None)
            if not cwd:
                config = getattr(self.executor, 'config', None)
                if config:
                    cwd = getattr(config, 'working_dir', None)
            if cwd and result.output:
                from orchestrator.core.file_extractor import (
                    extract_files_from_output,
                )

                files = extract_files_from_output(result.output, cwd)
                if files:
                    logger.info(
                        "files_extracted_from_output",
                        task_id=task.id,
                        count=len(files),
                        files=files,
                    )

            return result
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

    async def _heartbeat_loop(self, pipeline_id: str, task_id: str) -> None:
        """Emit heartbeat events every 10 seconds."""
        exec_start = time.monotonic()
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
            elapsed_ms = int((time.monotonic() - exec_start) * 1000)
            await self.event_bus.emit(
                OrchestratorEvent(
                    type=EventType.WORKER_HEARTBEAT,
                    task_id=pipeline_id,
                    node=self.worker_id,
                    data={
                        "worker_id": self.worker_id,
                        "lane": self.lane,
                        "elapsed_ms": elapsed_ms,
                        "timeout_ms": 300_000,
                        "current_task": task_id,
                    },
                )
            )

    async def _emit_heartbeat(self) -> None:
        """Emit a single heartbeat during idle polling."""
        elapsed_ms = int((time.monotonic() - self._start_time) * 1000)
        await self.event_bus.emit(
            OrchestratorEvent(
                type=EventType.WORKER_HEARTBEAT,
                node=self.worker_id,
                data={
                    "worker_id": self.worker_id,
                    "lane": self.lane,
                    "elapsed_ms": elapsed_ms,
                    "timeout_ms": 0,
                    "status": "idle",
                },
            )
        )

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

"""★ PoC 전용 — AgentWorker consumes tasks from TaskBoard lanes."""

from __future__ import annotations

import asyncio
import contextlib

import structlog

from orchestrator.adapters.base import CLIAdapter
from orchestrator.queue.board import TaskBoard

logger = structlog.get_logger()


class AgentWorker:
    """Consumes tasks from a specific lane on the TaskBoard.

    Each worker runs in an infinite loop, claiming tasks from its lane,
    executing them via a CLIAdapter, and reporting results back to the board.
    The worker only knows about the TaskBoard — not about other workers
    or the orchestrator. This is the loose coupling.
    """

    def __init__(
        self,
        worker_id: str,
        lane: str,
        adapter: CLIAdapter,
        board: TaskBoard,
    ) -> None:
        self.worker_id = worker_id
        self.lane = lane
        self.adapter = adapter
        self.board = board
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the worker loop as a background task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("worker_started", worker_id=self.worker_id, lane=self.lane)

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("worker_stopped", worker_id=self.worker_id)

    async def _run_loop(self) -> None:
        """Main worker loop: claim -> execute -> report."""
        while self._running:
            task = await self.board.claim(self.lane, timeout=2.0)
            if task is None:
                continue  # timeout, check if still running

            log = logger.bind(worker=self.worker_id, task_id=task.id, title=task.title)
            log.info("task_claimed")

            try:
                result = await self.adapter.run(
                    task.description or task.title,
                    timeout=self.adapter.config.timeout,
                )
                await self.board.complete(task.id, result.output)
                log.info("task_completed")
            except Exception as e:
                await self.board.fail(task.id, str(e))
                log.error("task_failed", error=str(e))

    @property
    def is_running(self) -> bool:
        return self._running

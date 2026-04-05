"""★ PoC 전용 — Hybrid orchestrator: LangGraph for planning, TaskBoard for execution."""

from __future__ import annotations

import asyncio
import uuid

import structlog

from orchestrator.adapters.factory import AdapterFactory
from orchestrator.events.bus import EventBus
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskItem, TaskState
from orchestrator.queue.worker import AgentWorker

logger = structlog.get_logger()

# Lanes that the hybrid orchestrator uses for decomposition.
_DEFAULT_LANES = ("plan", "implement", "review")


class HybridOrchestrator:
    """Combines LangGraph (planning) with TaskBoard (execution).

    Flow:
    1. User submits task
    2. LangGraph mini-graph: orchestrate -> decompose -> submit_to_board
    3. TaskBoard distributes subtasks to lanes
    4. AgentWorkers consume from lanes independently
    5. Orchestrator monitors completion via EventBus

    For PoC, decomposition is simulated (no real LLM call).
    """

    def __init__(
        self,
        board: TaskBoard,
        adapter_factory: AdapterFactory,
        event_bus: EventBus,
    ) -> None:
        self._board = board
        self._adapter_factory = adapter_factory
        self._event_bus = event_bus
        self._workers: list[AgentWorker] = []

        # Ensure default lanes exist
        for lane in _DEFAULT_LANES:
            self._board.add_lane(lane)

    async def submit(self, task: str, pipeline_id: str = "") -> list[str]:
        """Decompose task into subtasks and submit to TaskBoard.

        Returns list of submitted task IDs.

        For PoC, decomposition is simulated (not real LLM call):
        - Split into 3 subtasks: plan, implement, review
        - Set depends_on: implement depends on plan, review depends on implement
        - Submit all to board
        """
        if not pipeline_id:
            pipeline_id = uuid.uuid4().hex[:8]

        plan_id = uuid.uuid4().hex[:8]
        impl_id = uuid.uuid4().hex[:8]
        review_id = uuid.uuid4().hex[:8]

        subtasks = [
            TaskItem(
                id=plan_id,
                title=f"Plan: {task}",
                description=f"Create a plan for: {task}",
                lane="plan",
                depends_on=[],
                pipeline_id=pipeline_id,
            ),
            TaskItem(
                id=impl_id,
                title=f"Implement: {task}",
                description=f"Implement based on plan: {task}",
                lane="implement",
                depends_on=[plan_id],
                pipeline_id=pipeline_id,
            ),
            TaskItem(
                id=review_id,
                title=f"Review: {task}",
                description=f"Review implementation: {task}",
                lane="review",
                depends_on=[impl_id],
                pipeline_id=pipeline_id,
            ),
        ]

        submitted_ids: list[str] = []
        for sub in subtasks:
            await self._board.submit(sub)
            submitted_ids.append(sub.id)

        logger.info(
            "hybrid_tasks_submitted",
            task=task,
            pipeline_id=pipeline_id,
            task_ids=submitted_ids,
        )
        return submitted_ids

    async def start_workers(self, num_per_lane: int = 1) -> None:
        """Start AgentWorker instances for each lane.

        Uses MockCLIAdapter via AdapterFactory for PoC.
        """
        from orchestrator.models.schemas import AdapterConfig
        from orchestrator.poc.mock_adapters import MockCLIAdapter

        config = AdapterConfig(api_key="poc-key", timeout=30)

        for lane in _DEFAULT_LANES:
            for i in range(num_per_lane):
                adapter = MockCLIAdapter(
                    config=config,
                    responses={"default": f"[{lane}] completed successfully"},
                    latency_ms=10,
                )
                worker = AgentWorker(
                    worker_id=f"{lane}-worker-{i}",
                    lane=lane,
                    adapter=adapter,
                    board=self._board,
                )
                await worker.start()
                self._workers.append(worker)

        logger.info(
            "hybrid_workers_started",
            num_workers=len(self._workers),
            num_per_lane=num_per_lane,
        )

    async def stop_workers(self) -> None:
        """Stop all workers."""
        for worker in self._workers:
            await worker.stop()
        logger.info("hybrid_workers_stopped", num_workers=len(self._workers))
        self._workers.clear()

    async def wait_for_completion(
        self, task_ids: list[str], timeout: float = 60
    ) -> bool:
        """Wait until all submitted tasks reach DONE or FAILED.

        Returns True if all DONE, False if any FAILED or timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            all_terminal = True
            any_failed = False

            for tid in task_ids:
                task = self._board.get_task(tid)
                if task is None:
                    all_terminal = False
                    break
                if task.state == TaskState.FAILED:
                    any_failed = True
                elif task.state != TaskState.DONE:
                    all_terminal = False
                    break

            if all_terminal:
                return not any_failed

            await asyncio.sleep(0.05)

        return False

    def get_status(self) -> dict[str, object]:
        """Return board state + worker status."""
        return {
            "board": self._board.get_board_state(),
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "lane": w.lane,
                    "is_running": w.is_running,
                }
                for w in self._workers
            ],
        }

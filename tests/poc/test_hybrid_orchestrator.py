"""★ PoC 전용 — Tests for Hybrid orchestration model."""

from __future__ import annotations

import pytest

from orchestrator.adapters.factory import AdapterFactory
from orchestrator.events.bus import EventBus
from orchestrator.hybrid.orchestrator import HybridOrchestrator
from orchestrator.models.schemas import AdapterConfig, AgentResult
from orchestrator.poc.mock_adapters import MockCLIAdapter
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskState
from orchestrator.queue.worker import AgentWorker


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def board(event_bus: EventBus) -> TaskBoard:
    return TaskBoard(event_bus)


@pytest.fixture
def adapter_factory() -> AdapterFactory:
    return AdapterFactory(key_pool=None, mock_fallback=True)


@pytest.fixture
def orchestrator(
    board: TaskBoard,
    adapter_factory: AdapterFactory,
    event_bus: EventBus,
) -> HybridOrchestrator:
    return HybridOrchestrator(board=board, adapter_factory=adapter_factory, event_bus=event_bus)


class TestHybridOrchestrator:
    async def test_submit_creates_subtasks(
        self,
        orchestrator: HybridOrchestrator,
        board: TaskBoard,
    ) -> None:
        """submit() creates 3 TaskItems on the board: plan, implement, review."""
        task_ids = await orchestrator.submit("Build REST API")

        assert len(task_ids) == 3

        # All 3 tasks should exist on the board
        tasks = [board.get_task(tid) for tid in task_ids]
        assert all(t is not None for t in tasks)

        # Verify lanes
        assert tasks[0] is not None and tasks[0].lane == "plan"
        assert tasks[1] is not None and tasks[1].lane == "implement"
        assert tasks[2] is not None and tasks[2].lane == "review"

        # Verify titles contain the original task description
        assert tasks[0] is not None and "Plan:" in tasks[0].title
        assert tasks[1] is not None and "Implement:" in tasks[1].title
        assert tasks[2] is not None and "Review:" in tasks[2].title

        # Verify dependency chain
        assert tasks[0] is not None and tasks[0].depends_on == []
        assert tasks[1] is not None and tasks[1].depends_on == [task_ids[0]]
        assert tasks[2] is not None and tasks[2].depends_on == [task_ids[1]]

        # Plan should be TODO (no deps), others should be BACKLOG
        assert tasks[0] is not None and tasks[0].state == TaskState.TODO
        assert tasks[1] is not None and tasks[1].state == TaskState.BACKLOG
        assert tasks[2] is not None and tasks[2].state == TaskState.BACKLOG

    async def test_full_hybrid_pipeline(
        self,
        orchestrator: HybridOrchestrator,
        board: TaskBoard,
    ) -> None:
        """submit -> start_workers -> wait -> all tasks reach DONE."""
        task_ids = await orchestrator.submit("Implement login feature")

        await orchestrator.start_workers(num_per_lane=1)

        success = await orchestrator.wait_for_completion(task_ids, timeout=10)

        await orchestrator.stop_workers()

        assert success is True

        for tid in task_ids:
            task = board.get_task(tid)
            assert task is not None
            assert task.state == TaskState.DONE
            assert task.result != ""

    async def test_dependency_order_respected(
        self,
        orchestrator: HybridOrchestrator,
        board: TaskBoard,
    ) -> None:
        """Plan completes before implement starts, implement before review.

        This verifies that TaskBoard depends_on handles ordering,
        NOT LangGraph sequencing.
        """
        task_ids = await orchestrator.submit("Add search endpoint")

        await orchestrator.start_workers(num_per_lane=1)

        success = await orchestrator.wait_for_completion(task_ids, timeout=10)

        await orchestrator.stop_workers()

        assert success is True

        plan = board.get_task(task_ids[0])
        impl = board.get_task(task_ids[1])
        review = board.get_task(task_ids[2])

        assert plan is not None and impl is not None and review is not None

        # Verify temporal ordering via timestamps
        assert plan.completed_at is not None
        assert impl.started_at is not None
        assert impl.completed_at is not None
        assert review.started_at is not None

        assert plan.completed_at <= impl.started_at, (
            "implement started before plan completed"
        )
        assert impl.completed_at <= review.started_at, (
            "review started before implement completed"
        )

    async def test_worker_failure_retry(
        self,
        board: TaskBoard,
        adapter_factory: AdapterFactory,
        event_bus: EventBus,
    ) -> None:
        """Mock adapter fails once, then succeeds on retry.

        TaskBoard handles retry (re-queue on fail with retries left).
        """
        orch = HybridOrchestrator(
            board=board, adapter_factory=adapter_factory, event_bus=event_bus
        )

        task_ids = await orch.submit("Flaky feature")

        # We'll manually create workers with a custom adapter for the plan lane
        # that fails once then succeeds.
        config = AdapterConfig(api_key="test-key", timeout=30)

        call_count = 0

        class FailOnceMockAdapter(MockCLIAdapter):
            """Fails on first call, succeeds on subsequent calls."""

            async def run(
                self, prompt: str, *, timeout: int = 300, cwd: str | None = None
            ) -> AgentResult:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    msg = "Transient failure"
                    raise Exception(msg)
                return await super().run(prompt, timeout=timeout, cwd=cwd)

        fail_once_adapter = FailOnceMockAdapter(
            config=config,
            responses={"default": "recovered plan"},
            latency_ms=10,
        )

        # Start plan worker with fail-once adapter
        plan_worker = AgentWorker("plan-w", "plan", fail_once_adapter, board)
        await plan_worker.start()

        # Start normal workers for implement and review
        impl_adapter = MockCLIAdapter(
            config=config, responses={"default": "implemented"}, latency_ms=10
        )
        review_adapter = MockCLIAdapter(
            config=config, responses={"default": "reviewed"}, latency_ms=10
        )

        impl_worker = AgentWorker("impl-w", "implement", impl_adapter, board)
        review_worker = AgentWorker("review-w", "review", review_adapter, board)
        await impl_worker.start()
        await review_worker.start()

        success = await orch.wait_for_completion(task_ids, timeout=10)

        await plan_worker.stop()
        await impl_worker.stop()
        await review_worker.stop()

        assert success is True

        # Plan task should be DONE (succeeded after retry)
        plan_task = board.get_task(task_ids[0])
        assert plan_task is not None
        assert plan_task.state == TaskState.DONE
        assert plan_task.retry_count == 1  # failed once, retried

        # All tasks should be DONE
        for tid in task_ids:
            task = board.get_task(tid)
            assert task is not None
            assert task.state == TaskState.DONE

    async def test_multiple_tasks(
        self,
        orchestrator: HybridOrchestrator,
        board: TaskBoard,
    ) -> None:
        """Submit 2 tasks -> 6 subtasks -> all complete independently."""
        ids_1 = await orchestrator.submit("Build auth module")
        ids_2 = await orchestrator.submit("Build logging module")

        all_ids = ids_1 + ids_2
        assert len(all_ids) == 6

        await orchestrator.start_workers(num_per_lane=1)

        success = await orchestrator.wait_for_completion(all_ids, timeout=15)

        await orchestrator.stop_workers()

        assert success is True

        for tid in all_ids:
            task = board.get_task(tid)
            assert task is not None
            assert task.state == TaskState.DONE

        # Verify the two pipelines are independent —
        # they have different pipeline_ids
        pipeline_ids = {
            board.get_task(tid).pipeline_id  # type: ignore[union-attr]
            for tid in all_ids
        }
        assert len(pipeline_ids) == 2, "Two independent pipelines expected"

    async def test_get_status(
        self,
        orchestrator: HybridOrchestrator,
    ) -> None:
        """get_status() returns board state and worker info."""
        await orchestrator.submit("Status check task")

        status = orchestrator.get_status()

        assert "board" in status
        assert "workers" in status
        assert isinstance(status["workers"], list)
        assert len(status["workers"]) == 0  # no workers started yet

        await orchestrator.start_workers(num_per_lane=1)
        status = orchestrator.get_status()
        workers = status["workers"]
        assert isinstance(workers, list)
        assert len(workers) == 3  # one per lane

        await orchestrator.stop_workers()

    async def test_taskboard_not_langgraph_handles_ordering(
        self,
        orchestrator: HybridOrchestrator,
        board: TaskBoard,
    ) -> None:
        """Verify that TaskBoard depends_on handles sequencing.

        The HybridOrchestrator.submit() just creates tasks with depends_on.
        It does NOT use LangGraph edges for plan->implement->review ordering.
        The TaskBoard._try_promote() and _check_dependents() do the work.
        """
        # Use a fresh board to test dependency promotion directly
        event_bus = EventBus()
        fresh_board = TaskBoard(event_bus)
        fresh_orch = HybridOrchestrator(
            board=fresh_board,
            adapter_factory=AdapterFactory(key_pool=None, mock_fallback=True),
            event_bus=event_bus,
        )

        ids = await fresh_orch.submit("Ordering test")

        # Claim and complete plan manually
        plan_task = await fresh_board.claim("plan", timeout=1.0)
        assert plan_task is not None
        assert plan_task.id == ids[0]

        # impl should still be BACKLOG
        impl_task = fresh_board.get_task(ids[1])
        assert impl_task is not None
        assert impl_task.state == TaskState.BACKLOG

        # Complete plan -> TaskBoard should auto-promote impl to TODO
        await fresh_board.complete(plan_task.id, "plan result")

        impl_task = fresh_board.get_task(ids[1])
        assert impl_task is not None
        assert impl_task.state == TaskState.TODO, (
            "TaskBoard should promote impl after plan completes"
        )

        # review should still be BACKLOG (depends on impl, not plan)
        review_task = fresh_board.get_task(ids[2])
        assert review_task is not None
        assert review_task.state == TaskState.BACKLOG

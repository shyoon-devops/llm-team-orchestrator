"""★ PoC 전용 — E2E test for kanban task queue pipeline."""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.events.bus import EventBus
from orchestrator.events.types import OrchestratorEvent
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskItem, TaskState
from orchestrator.queue.worker import AgentWorker


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def board(event_bus: EventBus) -> TaskBoard:
    b = TaskBoard(event_bus)
    b.add_lane("plan")
    b.add_lane("implement")
    b.add_lane("review")
    return b


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test-key", timeout=30)


class TestKanbanE2E:
    async def test_full_kanban_pipeline(
        self,
        board: TaskBoard,
        event_bus: EventBus,
        config: AdapterConfig,
    ) -> None:
        """Simulate a full pipeline: plan -> implement -> review with dependencies."""
        # Track event order
        events: list[OrchestratorEvent] = []

        async def capture_event(event: OrchestratorEvent) -> None:
            events.append(event)

        event_bus.subscribe(capture_event)

        # Create mock adapters for each lane
        plan_adapter = MockCLIAdapter(
            config=config,
            responses={"default": "Plan: step 1, step 2"},
            latency_ms=10,
        )
        impl_adapter = MockCLIAdapter(
            config=config,
            responses={"default": "def main(): pass"},
            latency_ms=10,
        )
        review_adapter = MockCLIAdapter(
            config=config,
            responses={"default": "LGTM - approved"},
            latency_ms=10,
        )

        # Submit 3 tasks with dependency chain: plan -> implement -> review
        plan_task = TaskItem(
            id="plan-001",
            title="Design API",
            description="Design the REST API endpoints",
            lane="plan",
        )
        impl_task = TaskItem(
            id="impl-001",
            title="Implement API",
            description="Implement the designed API",
            lane="implement",
            depends_on=["plan-001"],
        )
        review_task = TaskItem(
            id="review-001",
            title="Review API",
            description="Review the implementation",
            lane="review",
            depends_on=["impl-001"],
        )

        # Submit all tasks — only plan should be promotable (no deps)
        await board.submit(plan_task)
        await board.submit(impl_task)
        await board.submit(review_task)

        # Verify initial states
        assert board.get_task("plan-001") is not None
        assert board.get_task("plan-001").state == TaskState.TODO  # type: ignore[union-attr]
        assert board.get_task("impl-001") is not None
        assert board.get_task("impl-001").state == TaskState.BACKLOG  # type: ignore[union-attr]
        assert board.get_task("review-001") is not None
        assert board.get_task("review-001").state == TaskState.BACKLOG  # type: ignore[union-attr]

        # Start 3 workers (one per lane)
        workers = [
            AgentWorker("plan-worker", "plan", plan_adapter, board),
            AgentWorker("impl-worker", "implement", impl_adapter, board),
            AgentWorker("review-worker", "review", review_adapter, board),
        ]

        for w in workers:
            await w.start()

        # Wait for all tasks to complete
        for _ in range(100):
            await asyncio.sleep(0.05)
            all_done = all(
                board.get_task(tid) is not None
                and board.get_task(tid).state == TaskState.DONE  # type: ignore[union-attr]
                for tid in ["plan-001", "impl-001", "review-001"]
            )
            if all_done:
                break

        for w in workers:
            await w.stop()

        # Verify all tasks completed
        for tid in ["plan-001", "impl-001", "review-001"]:
            t = board.get_task(tid)
            assert t is not None, f"Task {tid} not found"
            assert t.state == TaskState.DONE, f"Task {tid} state is {t.state}"

        # Verify results
        assert board.get_task("plan-001").result == "Plan: step 1, step 2"  # type: ignore[union-attr]
        assert board.get_task("impl-001").result == "def main(): pass"  # type: ignore[union-attr]
        assert board.get_task("review-001").result == "LGTM - approved"  # type: ignore[union-attr]

        # Verify dependency order was respected:
        # plan must complete before impl starts, impl before review starts
        plan_completed = board.get_task("plan-001").completed_at  # type: ignore[union-attr]
        impl_started = board.get_task("impl-001").started_at  # type: ignore[union-attr]
        impl_completed = board.get_task("impl-001").completed_at  # type: ignore[union-attr]
        review_started = board.get_task("review-001").started_at  # type: ignore[union-attr]

        assert plan_completed is not None
        assert impl_started is not None
        assert impl_completed is not None
        assert review_started is not None
        assert plan_completed <= impl_started, "impl started before plan completed"
        assert impl_completed <= review_started, "review started before impl completed"

        # Verify events were emitted (at least submitted, completed for each)
        event_data = [(e.data.get("task_event"), e.task_id) for e in events]
        for tid in ["plan-001", "impl-001", "review-001"]:
            assert ("task.completed", tid) in event_data, f"No completion event for {tid}"

        # Verify each adapter was called exactly once
        assert len(plan_adapter.call_log) == 1
        assert len(impl_adapter.call_log) == 1
        assert len(review_adapter.call_log) == 1

    async def test_board_state_after_completion(
        self,
        board: TaskBoard,
        config: AdapterConfig,
    ) -> None:
        """Board state correctly reflects all tasks in DONE column after pipeline."""
        adapter = MockCLIAdapter(
            config=config,
            responses={"default": "done"},
            latency_ms=10,
        )

        task = TaskItem(id="t1", title="single task", lane="plan")
        await board.submit(task)

        worker = AgentWorker("w1", "plan", adapter, board)
        await worker.start()

        for _ in range(50):
            await asyncio.sleep(0.05)
            t = board.get_task("t1")
            if t and t.state == TaskState.DONE:
                break

        await worker.stop()

        state = board.get_board_state()
        assert len(state["done"]) == 1
        assert state["done"][0]["id"] == "t1"
        assert len(state["backlog"]) == 0
        assert len(state["todo"]) == 0
        assert len(state["in_progress"]) == 0

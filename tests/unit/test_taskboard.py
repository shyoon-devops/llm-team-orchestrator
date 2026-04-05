"""Unit tests for TaskBoard and TaskItem."""

from __future__ import annotations

import pytest

from orchestrator.events.bus import EventBus
from orchestrator.events.types import OrchestratorEvent
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskItem, TaskState


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


def _make_task(
    lane: str = "implement",
    title: str = "test task",
    depends_on: list[str] | None = None,
    max_retries: int = 3,
    task_id: str | None = None,
) -> TaskItem:
    kwargs: dict[str, object] = {
        "lane": lane,
        "title": title,
        "max_retries": max_retries,
    }
    if depends_on is not None:
        kwargs["depends_on"] = depends_on
    if task_id is not None:
        kwargs["id"] = task_id
    return TaskItem(**kwargs)  # type: ignore[arg-type]


class TestTaskItem:
    def test_defaults(self) -> None:
        task = TaskItem(title="foo", lane="plan")
        assert task.state == TaskState.BACKLOG
        assert task.priority == 0
        assert task.depends_on == []
        assert task.assigned_to is None
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert len(task.id) == 8

    def test_custom_fields(self) -> None:
        task = TaskItem(
            title="bar",
            lane="review",
            priority=5,
            depends_on=["abc"],
            pipeline_id="pipe1",
        )
        assert task.priority == 5
        assert task.depends_on == ["abc"]
        assert task.pipeline_id == "pipe1"


class TestSubmit:
    async def test_submit_no_deps(self, board: TaskBoard) -> None:
        """Task with no dependencies goes to TODO immediately."""
        task = _make_task(title="no deps")
        task_id = await board.submit(task)

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.TODO

    async def test_submit_with_deps(self, board: TaskBoard) -> None:
        """Task with unresolved dependencies stays in BACKLOG."""
        task = _make_task(title="has deps", depends_on=["nonexistent"])
        task_id = await board.submit(task)

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.BACKLOG

    async def test_submit_auto_creates_lane(self, board: TaskBoard) -> None:
        """Submitting to a non-existent lane auto-creates it."""
        task = _make_task(lane="custom", title="custom lane task")
        task_id = await board.submit(task)

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.TODO


class TestClaim:
    async def test_claim_task(self, board: TaskBoard) -> None:
        """Agent claims a task, state becomes IN_PROGRESS."""
        task = _make_task(title="claimable")
        await board.submit(task)

        claimed = await board.claim("implement", timeout=1.0)
        assert claimed is not None
        assert claimed.state == TaskState.IN_PROGRESS
        assert claimed.started_at is not None

    async def test_claim_timeout(self, board: TaskBoard) -> None:
        """Claim returns None when no task is available within timeout."""
        result = await board.claim("implement", timeout=0.05)
        assert result is None

    async def test_claim_nonexistent_lane(self, board: TaskBoard) -> None:
        """Claim from a lane that doesn't exist returns None."""
        result = await board.claim("nonexistent", timeout=0.05)
        assert result is None


class TestComplete:
    async def test_complete_task(self, board: TaskBoard) -> None:
        """Completing a task sets state to DONE."""
        task = _make_task(title="to complete")
        task_id = await board.submit(task)
        await board.claim("implement", timeout=1.0)

        await board.complete(task_id, result="all good")

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.DONE
        assert stored.result == "all good"
        assert stored.completed_at is not None

    async def test_complete_promotes_dependents(self, board: TaskBoard) -> None:
        """Completing task A promotes task B that depends on A."""
        task_a = _make_task(title="task A", task_id="aaa")
        task_b = _make_task(title="task B", depends_on=["aaa"], task_id="bbb")

        await board.submit(task_a)
        await board.submit(task_b)

        # B should be in BACKLOG
        assert board.get_task("bbb") is not None
        assert board.get_task("bbb").state == TaskState.BACKLOG  # type: ignore[union-attr]

        # Claim and complete A
        await board.claim("implement", timeout=1.0)
        await board.complete("aaa", result="done")

        # B should now be promoted to TODO
        b = board.get_task("bbb")
        assert b is not None
        assert b.state == TaskState.TODO

    async def test_complete_nonexistent_raises(self, board: TaskBoard) -> None:
        """Completing a non-existent task raises KeyError."""
        with pytest.raises(KeyError):
            await board.complete("nonexistent", result="nope")


class TestFail:
    async def test_fail_with_retry(self, board: TaskBoard) -> None:
        """Failing a task with retries left re-queues it."""
        task = _make_task(title="retryable", max_retries=3)
        task_id = await board.submit(task)
        await board.claim("implement", timeout=1.0)

        await board.fail(task_id, error="oops")

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.TODO
        assert stored.retry_count == 1
        assert stored.error == "oops"

        # Should be re-claimable
        reclaimed = await board.claim("implement", timeout=1.0)
        assert reclaimed is not None
        assert reclaimed.id == task_id

    async def test_fail_max_retries(self, board: TaskBoard) -> None:
        """Failing a task that exceeded max retries marks it FAILED."""
        task = _make_task(title="doomed", max_retries=1)
        task_id = await board.submit(task)
        await board.claim("implement", timeout=1.0)

        await board.fail(task_id, error="fatal")

        stored = board.get_task(task_id)
        assert stored is not None
        assert stored.state == TaskState.FAILED
        assert stored.retry_count == 1
        assert stored.completed_at is not None

    async def test_fail_nonexistent_raises(self, board: TaskBoard) -> None:
        """Failing a non-existent task raises KeyError."""
        with pytest.raises(KeyError):
            await board.fail("nonexistent", error="nope")


class TestBoardState:
    async def test_get_board_state(self, board: TaskBoard) -> None:
        """Board state groups tasks by state correctly."""
        task1 = _make_task(title="task1", task_id="t1")
        task2 = _make_task(title="task2", depends_on=["t1"], task_id="t2")
        task3 = _make_task(title="task3", task_id="t3")

        await board.submit(task1)
        await board.submit(task2)
        await board.submit(task3)

        # t1 and t3 in TODO, t2 in BACKLOG
        state = board.get_board_state()
        assert len(state["todo"]) == 2
        assert len(state["backlog"]) == 1
        assert state["backlog"][0]["id"] == "t2"

    async def test_get_lane_tasks(self, board: TaskBoard) -> None:
        """get_lane_tasks returns only tasks in the specified lane."""
        await board.submit(_make_task(lane="plan", title="plan task"))
        await board.submit(_make_task(lane="implement", title="impl task"))

        plan_tasks = board.get_lane_tasks("plan")
        impl_tasks = board.get_lane_tasks("implement")

        assert len(plan_tasks) == 1
        assert plan_tasks[0].title == "plan task"
        assert len(impl_tasks) == 1
        assert impl_tasks[0].title == "impl task"


class TestMultipleLanes:
    async def test_multiple_lanes(self, board: TaskBoard) -> None:
        """Plan and implement lanes work independently."""
        plan_task = _make_task(lane="plan", title="plan it")
        impl_task = _make_task(lane="implement", title="build it")

        await board.submit(plan_task)
        await board.submit(impl_task)

        # Claim from plan lane
        claimed_plan = await board.claim("plan", timeout=1.0)
        assert claimed_plan is not None
        assert claimed_plan.title == "plan it"

        # Claim from implement lane
        claimed_impl = await board.claim("implement", timeout=1.0)
        assert claimed_impl is not None
        assert claimed_impl.title == "build it"

        # Each lane is now empty
        assert await board.claim("plan", timeout=0.05) is None
        assert await board.claim("implement", timeout=0.05) is None


class TestEvents:
    async def test_events_published(self, event_bus: EventBus) -> None:
        """Verify that task lifecycle events are published."""
        received: list[OrchestratorEvent] = []

        async def handler(event: OrchestratorEvent) -> None:
            received.append(event)

        event_bus.subscribe(handler)
        board = TaskBoard(event_bus)
        board.add_lane("implement")

        task = _make_task(title="event test", task_id="evt1")
        await board.submit(task)
        await board.claim("implement", timeout=1.0)
        await board.complete("evt1", result="ok")

        # Should have: submitted, promoted, claimed, completed
        task_events = [e.data.get("task_event") for e in received]
        assert "task.submitted" in task_events
        assert "task.promoted" in task_events
        assert "task.claimed" in task_events
        assert "task.completed" in task_events

    async def test_retry_event_published(self, event_bus: EventBus) -> None:
        """Verify that retry events are published."""
        received: list[OrchestratorEvent] = []

        async def handler(event: OrchestratorEvent) -> None:
            received.append(event)

        event_bus.subscribe(handler)
        board = TaskBoard(event_bus)
        board.add_lane("implement")

        task = _make_task(title="retry test", task_id="ret1", max_retries=2)
        await board.submit(task)
        await board.claim("implement", timeout=1.0)
        await board.fail("ret1", error="boom")

        task_events = [e.data.get("task_event") for e in received]
        assert "task.retried" in task_events


class TestDAGResolution:
    async def test_chain_dependency(self, board: TaskBoard) -> None:
        """A -> B -> C chain: C is promoted only after B completes."""
        a = _make_task(title="A", task_id="a1")
        b = _make_task(title="B", task_id="b1", depends_on=["a1"])
        c = _make_task(title="C", task_id="c1", depends_on=["b1"])

        await board.submit(a)
        await board.submit(b)
        await board.submit(c)

        assert board.get_task("a1").state == TaskState.TODO  # type: ignore[union-attr]
        assert board.get_task("b1").state == TaskState.BACKLOG  # type: ignore[union-attr]
        assert board.get_task("c1").state == TaskState.BACKLOG  # type: ignore[union-attr]

        # Complete A -> B promoted
        await board.claim("implement", timeout=1.0)
        await board.complete("a1", result="done")
        assert board.get_task("b1").state == TaskState.TODO  # type: ignore[union-attr]
        assert board.get_task("c1").state == TaskState.BACKLOG  # type: ignore[union-attr]

        # Complete B -> C promoted
        await board.claim("implement", timeout=1.0)
        await board.complete("b1", result="done")
        assert board.get_task("c1").state == TaskState.TODO  # type: ignore[union-attr]

    async def test_multi_dependency(self, board: TaskBoard) -> None:
        """C depends on both A and B: promoted only when both are done."""
        a = _make_task(title="A", task_id="m_a")
        b = _make_task(title="B", task_id="m_b")
        c = _make_task(title="C", task_id="m_c", depends_on=["m_a", "m_b"])

        await board.submit(a)
        await board.submit(b)
        await board.submit(c)

        # Complete A only - C should stay in BACKLOG
        await board.claim("implement", timeout=1.0)
        await board.complete("m_a", result="done")
        assert board.get_task("m_c").state == TaskState.BACKLOG  # type: ignore[union-attr]

        # Complete B - now C should be promoted
        await board.claim("implement", timeout=1.0)
        await board.complete("m_b", result="done")
        assert board.get_task("m_c").state == TaskState.TODO  # type: ignore[union-attr]

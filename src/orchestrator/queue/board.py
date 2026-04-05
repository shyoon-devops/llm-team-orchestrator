"""Kanban-style task board with per-lane asyncio queues."""

from __future__ import annotations

import asyncio
import time

import structlog

from orchestrator.events.bus import EventBus
from orchestrator.events.types import EventType, OrchestratorEvent
from orchestrator.queue.models import TaskItem, TaskState

logger = structlog.get_logger()

# Map task lifecycle actions to existing EventType values.
# The specific task event name is carried in data["task_event"].
_TASK_EVENT_MAP: dict[str, EventType] = {
    "task.submitted": EventType.NODE_STARTED,
    "task.promoted": EventType.NODE_STARTED,
    "task.claimed": EventType.NODE_STARTED,
    "task.completed": EventType.NODE_COMPLETED,
    "task.failed": EventType.NODE_FAILED,
    "task.retried": EventType.NODE_STARTED,
}


class TaskBoard:
    """Kanban-style task board with per-lane asyncio queues."""

    def __init__(self, event_bus: EventBus) -> None:
        self._tasks: dict[str, TaskItem] = {}
        self._lanes: dict[str, asyncio.Queue[str]] = {}
        self._lock = asyncio.Lock()
        self._event_bus = event_bus

    def add_lane(self, lane: str, maxsize: int = 0) -> None:
        """Register a lane (queue column)."""
        if lane not in self._lanes:
            self._lanes[lane] = asyncio.Queue(maxsize=maxsize)
            logger.info("lane_added", lane=lane, maxsize=maxsize)

    async def _publish_task_event(self, task_event: str, task: TaskItem) -> None:
        """Publish an event through the event bus for a task lifecycle action."""
        event_type = _TASK_EVENT_MAP.get(task_event, EventType.NODE_STARTED)
        await self._event_bus.publish(
            OrchestratorEvent(
                type=event_type,
                node=task.lane,
                task_id=task.id,
                data={
                    "task_event": task_event,
                    "title": task.title,
                    "state": task.state.value,
                    "lane": task.lane,
                },
            )
        )

    async def submit(self, task: TaskItem) -> str:
        """Submit a task to the board. Auto-promotes if no dependencies."""
        async with self._lock:
            # Ensure lane exists
            if task.lane not in self._lanes:
                self.add_lane(task.lane)

            self._tasks[task.id] = task
            logger.info("task_submitted", task_id=task.id, title=task.title, lane=task.lane)

        await self._publish_task_event("task.submitted", task)
        await self._try_promote(task)
        return task.id

    async def _try_promote(self, task: TaskItem) -> None:
        """Promote backlog -> todo if all dependencies are done."""
        async with self._lock:
            if task.state != TaskState.BACKLOG:
                return

            # Check if all dependencies are done
            for dep_id in task.depends_on:
                dep = self._tasks.get(dep_id)
                if dep is None or dep.state != TaskState.DONE:
                    return

            # All deps satisfied - promote
            task.state = TaskState.TODO
            await self._lanes[task.lane].put(task.id)
            logger.info("task_promoted", task_id=task.id, title=task.title)

        await self._publish_task_event("task.promoted", task)

    async def _check_dependents(self, completed_task_id: str) -> None:
        """After a task completes, check if any dependents can be promoted."""
        # Collect tasks that depend on the completed task (snapshot under lock)
        async with self._lock:
            dependents = [
                t
                for t in self._tasks.values()
                if completed_task_id in t.depends_on and t.state == TaskState.BACKLOG
            ]

        for dep_task in dependents:
            await self._try_promote(dep_task)

    async def claim(self, lane: str, timeout: float | None = None) -> TaskItem | None:
        """Agent claims a task from a lane. Returns None on timeout."""
        if lane not in self._lanes:
            return None

        try:
            if timeout is not None:
                task_id = await asyncio.wait_for(self._lanes[lane].get(), timeout=timeout)
            else:
                task_id = await asyncio.wait_for(self._lanes[lane].get(), timeout=30.0)
        except TimeoutError:
            return None

        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            task.state = TaskState.IN_PROGRESS
            task.started_at = time.time()

        logger.info("task_claimed", task_id=task_id, lane=lane)
        await self._publish_task_event("task.claimed", task)
        return task

    async def complete(self, task_id: str, result: str) -> None:
        """Mark task as done, trigger dependent promotion."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                msg = f"Task {task_id} not found"
                raise KeyError(msg)

            task.state = TaskState.DONE
            task.result = result
            task.completed_at = time.time()
            logger.info("task_completed", task_id=task_id, title=task.title)

        await self._publish_task_event("task.completed", task)
        await self._check_dependents(task_id)

    async def fail(self, task_id: str, error: str) -> None:
        """Mark task as failed. If retries left, re-queue it."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                msg = f"Task {task_id} not found"
                raise KeyError(msg)

            task.error = error
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                # Re-queue for retry
                task.state = TaskState.TODO
                task.started_at = None
                task.assigned_to = None
                await self._lanes[task.lane].put(task.id)
                logger.info(
                    "task_retried",
                    task_id=task_id,
                    retry_count=task.retry_count,
                    max_retries=task.max_retries,
                )
                await self._publish_task_event("task.retried", task)
            else:
                # Max retries exceeded
                task.state = TaskState.FAILED
                task.completed_at = time.time()
                logger.warning(
                    "task_failed",
                    task_id=task_id,
                    error=error,
                    retry_count=task.retry_count,
                )
                await self._publish_task_event("task.failed", task)

    def get_board_state(self) -> dict[str, list[dict[str, object]]]:
        """Return kanban board state grouped by state column."""
        result: dict[str, list[dict[str, object]]] = {
            state.value: [] for state in TaskState
        }
        for task in self._tasks.values():
            result[task.state.value].append(task.model_dump())
        return result

    def get_task(self, task_id: str) -> TaskItem | None:
        """Get a single task by ID."""
        return self._tasks.get(task_id)

    def get_lane_tasks(self, lane: str) -> list[TaskItem]:
        """Get all tasks in a lane."""
        return [t for t in self._tasks.values() if t.lane == lane]

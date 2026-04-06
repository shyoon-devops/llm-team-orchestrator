"""TaskBoard — kanban board-style task queue."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from orchestrator.core.queue.models import TaskItem, TaskState

logger = structlog.get_logger()


class TaskBoard:
    """칸반 보드 방식의 태스크 큐.

    레인별로 태스크를 관리하고, 의존성 기반 상태 전이를 처리한다.
    """

    def __init__(self, max_retries: int = 3) -> None:
        """
        Args:
            max_retries: 기본 최대 재시도 횟수.
        """
        self._tasks: dict[str, TaskItem] = {}
        self._lanes: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self._max_retries = max_retries

    async def submit(self, task: TaskItem) -> str:
        """새 태스크를 보드에 추가한다.

        Args:
            task: 추가할 태스크. state는 무시되고 BACKLOG로 설정됨.

        Returns:
            태스크 ID.

        Raises:
            ValueError: 동일한 ID의 태스크가 이미 존재하는 경우.
        """
        async with self._lock:
            if task.id in self._tasks:
                msg = f"Task already exists: {task.id}"
                raise ValueError(msg)

            task = task.model_copy(update={"state": TaskState.BACKLOG})

            # 레인 자동 생성
            if task.lane not in self._lanes:
                self._lanes[task.lane] = []
            self._lanes[task.lane].append(task.id)
            self._tasks[task.id] = task

            # 의존성이 없으면 즉시 TODO
            if not task.depends_on:
                self._tasks[task.id] = task.model_copy(update={"state": TaskState.TODO})

        logger.info("task_submitted", task_id=task.id, lane=task.lane)
        return task.id

    async def claim(self, lane: str, worker_id: str) -> TaskItem | None:
        """지정 레인에서 TODO 태스크를 가져와 IN_PROGRESS로 전이한다.

        Args:
            lane: 태스크를 가져올 레인 이름.
            worker_id: 요청하는 워커 ID.

        Returns:
            할당된 태스크. 가용 태스크가 없으면 None.
        """
        async with self._lock:
            task_ids = self._lanes.get(lane, [])
            # 우선순위 내림차순으로 TODO 태스크 검색
            candidates = [
                self._tasks[tid] for tid in task_ids if self._tasks[tid].state == TaskState.TODO
            ]
            candidates.sort(key=lambda t: t.priority, reverse=True)

            if not candidates:
                return None

            task = candidates[0]
            self._tasks[task.id] = task.model_copy(
                update={
                    "state": TaskState.IN_PROGRESS,
                    "assigned_to": worker_id,
                    "started_at": datetime.utcnow(),
                }
            )
            return self._tasks[task.id]

    async def complete(self, task_id: str, result: str) -> None:
        """태스크를 성공 완료 처리한다.

        Args:
            task_id: 완료할 태스크 ID.
            result: 실행 결과 텍스트.

        Raises:
            KeyError: 태스크 ID가 존재하지 않는 경우.
            ValueError: 태스크가 IN_PROGRESS 상태가 아닌 경우.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                msg = f"Task not found: {task_id}"
                raise KeyError(msg)
            if task.state != TaskState.IN_PROGRESS:
                msg = f"Task {task_id} is not in IN_PROGRESS state: {task.state}"
                raise ValueError(msg)

            self._tasks[task_id] = task.model_copy(
                update={
                    "state": TaskState.DONE,
                    "result": result,
                    "completed_at": datetime.utcnow(),
                }
            )

            # 의존 태스크 상태 전이 확인
            self._check_dependencies()

        logger.info("task_completed", task_id=task_id)

    async def fail(self, task_id: str, error: str) -> None:
        """태스크를 실패 처리한다. 재시도 가능하면 TODO로 되돌린다.

        Args:
            task_id: 실패할 태스크 ID.
            error: 에러 메시지.

        Raises:
            KeyError: 태스크 ID가 존재하지 않는 경우.
            ValueError: 태스크가 IN_PROGRESS 상태가 아닌 경우.
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                msg = f"Task not found: {task_id}"
                raise KeyError(msg)
            if task.state != TaskState.IN_PROGRESS:
                msg = f"Task {task_id} is not in IN_PROGRESS state: {task.state}"
                raise ValueError(msg)

            new_retry_count = task.retry_count + 1
            if new_retry_count < task.max_retries:
                # 재시도 가능
                self._tasks[task_id] = task.model_copy(
                    update={
                        "state": TaskState.TODO,
                        "assigned_to": None,
                        "retry_count": new_retry_count,
                        "error": error,
                    }
                )
                logger.info(
                    "task_retrying",
                    task_id=task_id,
                    retry_count=new_retry_count,
                    max_retries=task.max_retries,
                )
            else:
                # 재시도 횟수 초과
                self._tasks[task_id] = task.model_copy(
                    update={
                        "state": TaskState.FAILED,
                        "error": error,
                        "retry_count": new_retry_count,
                        "completed_at": datetime.utcnow(),
                    }
                )
                logger.warning("task_failed", task_id=task_id, error=error)
                # Cascade failure: 의존자도 FAILED로 전이
                self._cascade_failure(task_id)

    def _cascade_failure(self, failed_id: str) -> None:
        """failed 태스크에 의존하는 BACKLOG 태스크를 재귀적으로 FAILED 처리."""
        for tid, task in self._tasks.items():
            if (
                failed_id in task.depends_on
                and task.state == TaskState.BACKLOG
            ):
                self._tasks[tid] = task.model_copy(
                    update={
                        "state": TaskState.FAILED,
                        "error": f"Dependency failed: {failed_id}",
                        "completed_at": datetime.utcnow(),
                    }
                )
                logger.warning(
                    "task_cascade_failed",
                    task_id=tid,
                    dependency=failed_id,
                )
                self._cascade_failure(tid)

    def _check_dependencies(self) -> None:
        """BACKLOG 태스크의 의존성을 확인하고 충족 시 TODO로 전이한다."""
        for task_id, task in self._tasks.items():
            if task.state != TaskState.BACKLOG:
                continue
            if not task.depends_on:
                continue
            all_done = all(
                self._tasks.get(dep_id, task).state == TaskState.DONE for dep_id in task.depends_on
            )
            if all_done:
                self._tasks[task_id] = task.model_copy(update={"state": TaskState.TODO})

    def get_board_state(self) -> dict[str, Any]:
        """칸반 보드의 전체 상태를 반환한다.

        Returns:
            레인별 태스크 상태.
        """
        lanes: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for lane_name in self._lanes:
            lanes[lane_name] = {state.value: [] for state in TaskState}
        for task in self._tasks.values():
            if task.lane in lanes:
                lanes[task.lane][task.state.value].append(task.model_dump())

        # 요약
        by_state: dict[str, int] = {state.value: 0 for state in TaskState}
        for task in self._tasks.values():
            by_state[task.state.value] += 1

        return {
            "lanes": lanes,
            "summary": {
                "total": len(self._tasks),
                "by_state": by_state,
            },
        }

    def add_lane(self, lane: str) -> None:
        """새 레인을 추가한다.

        Args:
            lane: 레인 이름.

        Raises:
            ValueError: 이미 존재하는 레인 이름인 경우.
        """
        if lane in self._lanes:
            msg = f"Lane already exists: {lane}"
            raise ValueError(msg)
        self._lanes[lane] = []

    def get_task(self, task_id: str) -> TaskItem | None:
        """ID로 태스크를 조회한다.

        Args:
            task_id: 태스크 ID.

        Returns:
            태스크 인스턴스. 없으면 None.
        """
        return self._tasks.get(task_id)

    def get_lane_tasks(
        self,
        lane: str,
        state: TaskState | None = None,
    ) -> list[TaskItem]:
        """특정 레인의 태스크 목록을 반환한다.

        Args:
            lane: 레인 이름.
            state: 상태 필터. None이면 전체.

        Returns:
            태스크 목록 (우선순위 내림차순).
        """
        task_ids = self._lanes.get(lane, [])
        tasks = [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        if state is not None:
            tasks = [t for t in tasks if t.state == state]
        tasks.sort(key=lambda t: t.priority, reverse=True)
        return tasks

    def is_all_done(self, pipeline_id: str) -> bool:
        """특정 파이프라인의 모든 태스크가 터미널 상태인지 확인한다.

        Args:
            pipeline_id: 파이프라인 ID.

        Returns:
            모든 태스크가 DONE/FAILED이면 True.
        """
        pipeline_tasks = [t for t in self._tasks.values() if t.pipeline_id == pipeline_id]
        if not pipeline_tasks:
            return True
        return all(t.state in (TaskState.DONE, TaskState.FAILED) for t in pipeline_tasks)

    def get_results(self, pipeline_id: str) -> list[TaskItem]:
        """특정 파이프라인의 완료된 태스크(DONE)를 반환한다.

        Args:
            pipeline_id: 파이프라인 ID.

        Returns:
            DONE 상태의 태스크 목록.
        """
        return [
            t
            for t in self._tasks.values()
            if t.pipeline_id == pipeline_id and t.state == TaskState.DONE
        ]

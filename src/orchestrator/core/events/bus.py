"""EventBus — pub/sub event distribution."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

import structlog

from orchestrator.core.events.types import OrchestratorEvent

logger = structlog.get_logger()

Callback = Callable[[OrchestratorEvent], Any]


class EventBus:
    """비동기 이벤트 버스.

    OrchestratorEvent를 발행(emit)하고, 등록된 콜백(subscribe)에 전달한다.
    sync/async 콜백 모두 지원한다.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callback] = []
        self._history: list[OrchestratorEvent] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callback) -> None:
        """이벤트 콜백을 등록한다.

        Args:
            callback: 이벤트 수신 콜백. sync 또는 async 함수 모두 가능.
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callback) -> None:
        """이벤트 콜백을 제거한다.

        Args:
            callback: 제거할 콜백.
        """
        self._subscribers = [s for s in self._subscribers if s is not callback]

    async def emit(self, event: OrchestratorEvent) -> None:
        """이벤트를 발행하고 모든 구독자에게 전달한다.

        Args:
            event: 발행할 이벤트.
        """
        async with self._lock:
            self._history.append(event)

        for callback in self._subscribers:
            try:
                result = callback(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "event_callback_error",
                    event_type=event.type,
                    task_id=event.task_id,
                )

    def get_history(
        self,
        task_id: str | None = None,
    ) -> list[OrchestratorEvent]:
        """이벤트 히스토리를 조회한다.

        Args:
            task_id: 특정 파이프라인의 이벤트만 필터링. None이면 전체.

        Returns:
            이벤트 목록 (시간순).
        """
        if task_id is None:
            return list(self._history)
        return [e for e in self._history if e.task_id == task_id]

    def clear_history(self) -> None:
        """이벤트 히스토리를 초기화한다."""
        self._history.clear()

"""Async event bus for orchestrator observability."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from orchestrator.events.types import OrchestratorEvent

logger = structlog.get_logger()


class EventBus:
    """asyncio-based pub/sub event bus."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[OrchestratorEvent], Coroutine[Any, Any, None]]] = []
        self._history: list[OrchestratorEvent] = []

    def subscribe(self, handler: Callable[[OrchestratorEvent], Coroutine[Any, Any, None]]) -> None:
        self._subscribers.append(handler)

    def unsubscribe(
        self, handler: Callable[[OrchestratorEvent], Coroutine[Any, Any, None]]
    ) -> None:
        self._subscribers = [s for s in self._subscribers if s is not handler]

    async def publish(self, event: OrchestratorEvent) -> None:
        self._history.append(event)
        logger.debug("event_published", event_type=event.type.value, node=event.node)
        tasks = [sub(event) for sub in self._subscribers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def history(self) -> list[OrchestratorEvent]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

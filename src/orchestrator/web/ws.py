"""★ PoC 전용 — WebSocket event broadcaster."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from orchestrator.events.bus import EventBus
    from orchestrator.events.types import OrchestratorEvent

logger = structlog.get_logger()


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self, event_bus: EventBus) -> None:
        self._connections: list[WebSocket] = []
        event_bus.subscribe(self._broadcast)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("ws_client_connected", total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("ws_client_disconnected", total=len(self._connections))

    async def _broadcast(self, event: OrchestratorEvent) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(event.model_dump())
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

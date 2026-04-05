"""WebSocket event stream."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orchestrator.core.events.types import OrchestratorEvent

logger = structlog.get_logger()

ws_router = APIRouter()


class WebSocketManager:
    """WebSocket 연결 관리자."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """WebSocket 연결을 수락하고 등록한다."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("ws_connected", total=len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """WebSocket 연결을 제거한다."""
        async with self._lock:
            self._connections = [c for c in self._connections if c is not websocket]
        logger.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, event: OrchestratorEvent) -> None:
        """모든 연결에 이벤트를 브로드캐스트한다."""
        message = event.model_dump_json()
        disconnected: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            await self.disconnect(ws)


_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """WebSocketManager 싱글턴을 반환한다."""
    return _manager


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """WebSocket 이벤트 스트림 핸들러."""
    await _manager.connect(websocket)
    try:
        # Send connection established message
        await websocket.send_json(
            {
                "type": "connection.established",
                "payload": {
                    "server_version": "0.1.0",
                    "protocol_version": "1",
                },
            }
        )
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Client messages are acknowledged but not processed in Phase 1
            logger.debug("ws_received", data=data[:100])
    except WebSocketDisconnect:
        await _manager.disconnect(websocket)
    except Exception:
        await _manager.disconnect(websocket)

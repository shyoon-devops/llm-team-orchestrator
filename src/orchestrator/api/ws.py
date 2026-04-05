"""WebSocket event stream.

Spec (websocket-protocol.md):
- Server messages: {"type": "...", "timestamp": "...", "payload": {...}}
- Client actions: subscribe, unsubscribe, ping
- Subscription filtering: pipeline_id, event_types
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orchestrator import __version__
from orchestrator.core.events.types import OrchestratorEvent
from orchestrator.core.utils import generate_id

logger = structlog.get_logger()

ws_router = APIRouter()


@dataclass
class _ClientSubscription:
    """Per-client subscription filter."""

    pipeline_id: str | None = None
    event_types: list[str] | None = None


@dataclass
class _ConnectedClient:
    """A connected WebSocket client with subscription state."""

    ws: WebSocket
    client_id: str = ""
    subscription: _ClientSubscription = field(default_factory=_ClientSubscription)


class WebSocketManager:
    """WebSocket 연결 관리자.

    Handles connection lifecycle, subscription filtering, and spec-compliant
    message formatting.
    """

    def __init__(self) -> None:
        self._clients: list[_ConnectedClient] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> _ConnectedClient:
        """WebSocket 연결을 수락하고 등록한다."""
        await websocket.accept()
        client_id = generate_id("ws")
        client = _ConnectedClient(ws=websocket, client_id=client_id)
        async with self._lock:
            self._clients.append(client)
        logger.info("ws_connected", client_id=client_id, total=len(self._clients))
        return client

    async def disconnect(self, client: _ConnectedClient) -> None:
        """WebSocket 연결을 제거한다."""
        async with self._lock:
            self._clients = [c for c in self._clients if c is not client]
        logger.info("ws_disconnected", client_id=client.client_id, total=len(self._clients))

    def _matches_subscription(
        self,
        client: _ConnectedClient,
        event: OrchestratorEvent,
    ) -> bool:
        """Check if an event matches the client's subscription filter."""
        sub = client.subscription

        # No filter → receive everything
        if sub.pipeline_id is None and sub.event_types is None:
            return True

        # Pipeline ID filter
        if sub.pipeline_id is not None and event.task_id != sub.pipeline_id:
            return False

        # Event type filter
        return sub.event_types is None or event.type.value in sub.event_types

    @staticmethod
    def _format_event(event: OrchestratorEvent) -> str:
        """Format OrchestratorEvent to spec-compliant WS message.

        Spec format: {"type": "...", "timestamp": "...", "payload": {...}}
        """
        payload = {
            "pipeline_id": event.task_id,
            **event.data,
        }
        msg = {
            "type": event.type.value,
            "timestamp": event.timestamp.isoformat() + "Z"
            if not event.timestamp.tzinfo
            else event.timestamp.isoformat(),
            "payload": payload,
        }
        return json.dumps(msg, ensure_ascii=False, default=str)

    async def broadcast(self, event: OrchestratorEvent) -> None:
        """모든 구독 매칭 연결에 이벤트를 브로드캐스트한다."""
        message = self._format_event(event)
        disconnected: list[_ConnectedClient] = []
        for client in self._clients:
            if not self._matches_subscription(client, event):
                continue
            try:
                await client.ws.send_text(message)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            await self.disconnect(client)

    async def handle_client_message(
        self,
        client: _ConnectedClient,
        raw: str,
    ) -> None:
        """Process incoming client message (subscribe/unsubscribe/ping)."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(client, "INVALID_JSON", "올바른 JSON 형식이 아닙니다.")
            return

        action = data.get("action")
        payload = data.get("payload", {})

        if action == "subscribe":
            client.subscription = _ClientSubscription(
                pipeline_id=payload.get("pipeline_id"),
                event_types=payload.get("event_types"),
            )
            await self._send_message(
                client,
                {
                    "type": "subscription.confirmed",
                    "timestamp": _now_iso(),
                    "payload": {
                        "pipeline_id": client.subscription.pipeline_id,
                        "event_types": client.subscription.event_types,
                    },
                },
            )
        elif action == "unsubscribe":
            client.subscription = _ClientSubscription()
            await self._send_message(
                client,
                {
                    "type": "subscription.cleared",
                    "timestamp": _now_iso(),
                    "payload": {},
                },
            )
        elif action == "ping":
            await self._send_message(
                client,
                {
                    "type": "pong",
                    "timestamp": _now_iso(),
                    "payload": {},
                },
            )
        else:
            await self._send_error(
                client,
                "INVALID_ACTION",
                f"알 수 없는 action: '{action}'",
            )

    async def _send_message(
        self,
        client: _ConnectedClient,
        msg: dict[str, object],
    ) -> None:
        """Send a JSON message to a specific client."""
        try:
            await client.ws.send_json(msg)
        except Exception:
            logger.warning("ws_send_failed", client_id=client.client_id)

    async def _send_error(
        self,
        client: _ConnectedClient,
        code: str,
        message: str,
    ) -> None:
        """Send an error response to a client."""
        await self._send_message(
            client,
            {
                "type": "connection.error",
                "timestamp": _now_iso(),
                "payload": {"code": code, "message": message},
            },
        )


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(tz=UTC).isoformat()


_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """WebSocketManager 싱글턴을 반환한다."""
    return _manager


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """WebSocket 이벤트 스트림 핸들러."""
    client = await _manager.connect(websocket)
    try:
        # Send connection established message
        await websocket.send_json(
            {
                "type": "connection.established",
                "timestamp": _now_iso(),
                "payload": {
                    "server_version": __version__,
                    "protocol_version": "1",
                    "client_id": client.client_id,
                },
            }
        )
        # Listen for client messages
        while True:
            raw = await websocket.receive_text()
            await _manager.handle_client_message(client, raw)
    except WebSocketDisconnect:
        await _manager.disconnect(client)
    except Exception:
        await _manager.disconnect(client)

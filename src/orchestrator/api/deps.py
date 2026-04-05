"""FastAPI dependency injection."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.bus import EventBus

_engine: OrchestratorEngine | None = None


def set_engine(engine: OrchestratorEngine) -> None:
    """Engine 싱글턴을 설정한다.

    Args:
        engine: OrchestratorEngine 인스턴스.
    """
    global _engine
    _engine = engine


def get_engine(request: Request | None = None) -> OrchestratorEngine:
    """Engine 싱글턴을 반환한다.

    Args:
        request: FastAPI Request (lifespan에서 설정한 engine 참조용).

    Returns:
        OrchestratorEngine 인스턴스.

    Raises:
        RuntimeError: Engine이 초기화되지 않은 경우.
    """
    if request is not None:
        engine: Any = getattr(request.app.state, "engine", None)
        if engine is not None:
            return engine  # type: ignore[no-any-return]
    if _engine is not None:
        return _engine
    msg = "OrchestratorEngine not initialized. Call set_engine() or use lifespan."
    raise RuntimeError(msg)


def get_event_bus(request: Request | None = None) -> EventBus:
    """EventBus 인스턴스를 반환한다.

    Args:
        request: FastAPI Request.

    Returns:
        EventBus 인스턴스.
    """
    engine = get_engine(request)
    return engine.event_bus

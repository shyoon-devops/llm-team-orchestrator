"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from orchestrator.api.deps import set_engine
from orchestrator.api.routes import router
from orchestrator.api.ws import get_ws_manager, ws_router
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.errors.exceptions import OrchestratorError

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작/종료 시 Engine 생명주기를 관리한다."""
    engine = OrchestratorEngine()
    app.state.engine = engine
    set_engine(engine)

    # Register WS broadcast as event subscriber
    ws_manager = get_ws_manager()
    engine.subscribe(ws_manager.broadcast)

    await engine.start()
    logger.info("engine_started")
    yield
    await engine.shutdown()
    logger.info("engine_stopped")


async def orchestrator_error_handler(
    request: Request,
    exc: OrchestratorError,
) -> JSONResponse:
    """OrchestratorError 계열 예외를 spec 형식으로 변환한다.

    Spec (api-spec.md §2):
    {"error": {"code": "CLI_TIMEOUT", "message": "...", "details": {...}}}
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.user_message,
                "details": exc.details,
            }
        },
    )


def create_app() -> FastAPI:
    """FastAPI 앱을 생성한다.

    Returns:
        구성된 FastAPI 인스턴스.
    """
    app = FastAPI(
        title="Agent Team Orchestrator",
        version="1.0.0",
        description="Multi-LLM agent team orchestrator API",
        lifespan=lifespan,
    )

    # Exception handler: OrchestratorError → spec error format
    app.add_exception_handler(OrchestratorError, orchestrator_error_handler)  # type: ignore[arg-type]

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(router)
    app.include_router(ws_router)

    return app


app = create_app()

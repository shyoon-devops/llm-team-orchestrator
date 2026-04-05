"""API test conftest."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.api.app import create_app
from orchestrator.api.deps import set_engine
from orchestrator.core.engine import OrchestratorEngine


@pytest.fixture
async def engine():
    """테스트용 OrchestratorEngine 인스턴스."""
    return OrchestratorEngine()


@pytest.fixture
async def async_client(engine):
    """httpx AsyncClient for testing."""
    app = create_app()
    app.state.engine = engine
    set_engine(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

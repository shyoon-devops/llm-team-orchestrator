"""API test conftest."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from orchestrator.api.app import create_app
from orchestrator.api.deps import set_engine
from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine


@pytest.fixture
async def engine(tmp_path):
    """테스트용 OrchestratorEngine 인스턴스."""
    config = OrchestratorConfig(
        checkpoint_enabled=True,
        checkpoint_db_path=str(tmp_path / "test_checkpoints.sqlite"),
    )
    return OrchestratorEngine(config=config)


@pytest.fixture
async def async_client(engine):
    """httpx AsyncClient for testing."""
    app = create_app()
    app.state.engine = engine
    set_engine(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

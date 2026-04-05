"""Unit test conftest."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from orchestrator.core.engine import OrchestratorEngine, _ORCHESTRATOR_PATH


@pytest_asyncio.fixture
async def protection_engine() -> AsyncIterator[OrchestratorEngine]:
    """Engine fixture for protection-focused tests."""
    engine = OrchestratorEngine()
    await engine.start()
    try:
        yield engine
    finally:
        await engine.shutdown()


@pytest.fixture
def orchestrator_dir() -> Path:
    """Resolved orchestrator project root."""
    return _ORCHESTRATOR_PATH

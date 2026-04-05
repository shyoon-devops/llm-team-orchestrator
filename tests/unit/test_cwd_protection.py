"""Tests for V2-1: cwd self-protection — orchestrator directory guard."""

from __future__ import annotations

import os

import pytest

from orchestrator.core.engine import _ORCHESTRATOR_DIR, OrchestratorEngine


async def test_submit_task_rejects_orchestrator_dir() -> None:
    """submit_task with target_repo=orchestrator_dir should raise ValueError."""
    engine = OrchestratorEngine()
    await engine.start()

    try:
        with pytest.raises(ValueError, match="CLI cannot run in orchestrator directory"):
            await engine.submit_task(
                "build something",
                target_repo=_ORCHESTRATOR_DIR,
            )
    finally:
        await engine.shutdown()


async def test_submit_task_rejects_orchestrator_dir_realpath(tmp_path: object) -> None:
    """symlink to orchestrator dir should also be rejected."""
    engine = OrchestratorEngine()
    await engine.start()

    # Create a symlink pointing to orchestrator directory
    link_path = str(tmp_path) + "/orch-link"  # type: ignore[operator]
    try:
        os.symlink(_ORCHESTRATOR_DIR, link_path)
    except OSError:
        pytest.skip("Cannot create symlinks on this platform")

    try:
        with pytest.raises(ValueError, match="CLI cannot run in orchestrator directory"):
            await engine.submit_task(
                "build something",
                target_repo=link_path,
            )
    finally:
        await engine.shutdown()


async def test_submit_task_allows_different_dir(tmp_path: object) -> None:
    """submit_task with a different target_repo should not raise."""
    engine = OrchestratorEngine()
    await engine.start()

    try:
        # This will proceed to planning phase (and may fail there due to no
        # team preset, but it should NOT fail with the cwd protection error)
        target = str(tmp_path) + "/my-project"  # type: ignore[operator]
        os.makedirs(target, exist_ok=True)
        pipeline = await engine.submit_task(
            "hello world",
            target_repo=target,
        )
        assert pipeline is not None
        assert pipeline.task_id != ""
    finally:
        await engine.shutdown()


def test_orchestrator_dir_is_correct() -> None:
    """_ORCHESTRATOR_DIR should point to the src parent (project root)."""
    # engine.py is at src/orchestrator/core/engine.py
    # so parent.parent.parent.parent = project root (4 levels up)
    assert os.path.isdir(_ORCHESTRATOR_DIR)
    # Should contain pyproject.toml or src/ directory
    assert os.path.isdir(os.path.join(_ORCHESTRATOR_DIR, "src")) or os.path.isfile(
        os.path.join(_ORCHESTRATOR_DIR, "pyproject.toml")
    )

"""Tests for V2-1: cwd self-protection — orchestrator directory guard."""

from __future__ import annotations

import os
from pathlib import Path

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


async def test_submit_task_rejects_orchestrator_dir_realpath(tmp_path: Path) -> None:
    """symlink to orchestrator dir should also be rejected."""
    engine = OrchestratorEngine()
    await engine.start()

    # Create a symlink pointing to orchestrator directory
    link_path = tmp_path / "orch-link"
    try:
        os.symlink(_ORCHESTRATOR_DIR, link_path)
    except OSError:
        pytest.skip("Cannot create symlinks on this platform")

    try:
        with pytest.raises(ValueError, match="CLI cannot run in orchestrator directory"):
            await engine.submit_task(
                "build something",
                target_repo=str(link_path),
            )
    finally:
        await engine.shutdown()


async def test_submit_task_rejects_orchestrator_subdirectory() -> None:
    """orchestrator 하위 디렉토리도 target_repo로 허용하지 않는다."""
    engine = OrchestratorEngine()
    await engine.start()

    try:
        with pytest.raises(ValueError, match="CLI cannot run in orchestrator directory"):
            await engine.submit_task(
                "build something",
                target_repo=os.path.join(_ORCHESTRATOR_DIR, "src"),
            )
    finally:
        await engine.shutdown()


async def test_submit_task_rejects_orchestrator_dir_relative_path() -> None:
    """상대 경로가 orchestrator 디렉토리로 해석되면 거부한다."""
    engine = OrchestratorEngine()
    await engine.start()

    original_cwd = os.getcwd()
    os.chdir(_ORCHESTRATOR_DIR)

    try:
        with pytest.raises(ValueError, match="CLI cannot run in orchestrator directory"):
            await engine.submit_task(
                "build something",
                target_repo="./src/..",
            )
    finally:
        os.chdir(original_cwd)
        await engine.shutdown()


async def test_submit_task_allows_different_dir(tmp_path: Path) -> None:
    """submit_task with a different target_repo should not raise."""
    engine = OrchestratorEngine()
    await engine.start()

    try:
        # This will proceed to planning phase (and may fail there due to no
        # team preset, but it should NOT fail with the cwd protection error)
        target = tmp_path / "my-project"
        target.mkdir(exist_ok=True)
        pipeline = await engine.submit_task(
            "hello world",
            target_repo=str(target),
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


def test_is_protected_target_repo_rejects_orchestrator_path_objects() -> None:
    """보호 경로 판정은 Path 입력을 문자열로 변환한 경우에도 동일해야 한다."""
    assert OrchestratorEngine._is_protected_target_repo(str(Path(_ORCHESTRATOR_DIR)))
    assert OrchestratorEngine._is_protected_target_repo(
        str(Path(_ORCHESTRATOR_DIR) / "tests")
    )


def test_is_protected_target_repo_allows_parent_and_sibling_paths(tmp_path: Path) -> None:
    """저장소 바깥 경로는 보호 대상으로 오인하지 않는다."""
    sibling_repo = tmp_path / "sibling-repo"
    sibling_repo.mkdir()

    assert not OrchestratorEngine._is_protected_target_repo(str(Path(_ORCHESTRATOR_DIR).parent))
    assert not OrchestratorEngine._is_protected_target_repo(str(sibling_repo))

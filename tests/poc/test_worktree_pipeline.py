"""★ PoC 전용 — Worktree pipeline integration tests.

Tests A: target_repo → worktree → cwd → filediff → cleanup
Tests B: worktree merge into main after pipeline
Tests C: concurrent pipelines with task_id isolation
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from orchestrator.config.schema import AgentDef, OrchestratorConfig
from orchestrator.web.app import AppState


def _create_test_repo(base: Path) -> str:
    """Create a minimal git repo for testing."""
    repo = base / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    r = str(repo)
    subprocess.run(["git", "init"], cwd=r, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=r, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=r, capture_output=True, check=True
    )
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "-A"], cwd=r, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=r, capture_output=True, check=True)
    return r


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        agents={
            "planner": AgentDef(cli="mock", role="architect", timeout=30),
            "implementer": AgentDef(cli="mock", role="engineer", timeout=30),
            "reviewer": AgentDef(cli="mock", role="reviewer", timeout=30),
        }
    )


class TestWorktreePipeline:
    """A: run_pipeline(target_repo=...) creates worktree, runs CLI in it, cleans up."""

    async def test_pipeline_with_target_repo(
        self, tmp_path: Path, mock_config: OrchestratorConfig
    ) -> None:
        repo = _create_test_repo(tmp_path)
        state = AppState(mock_config)

        task_id = "wt-test-01"
        await state.run_pipeline(task_id, "Add a hello function", target_repo=repo)

        # Pipeline should complete (mock adapter → reviewed → merge is best-effort)
        pipeline = state.pipelines[task_id]
        assert pipeline.status.value == "completed"

        # Worktree should be cleaned up
        worktree_dir = Path(repo) / ".worktrees" / f"pipeline-{task_id}"
        assert not worktree_dir.exists(), "Worktree should be cleaned up"

        # Events should include pipeline lifecycle
        event_types = [e.type.value for e in state.event_bus.history]
        assert "pipeline.started" in event_types
        assert "pipeline.completed" in event_types

    async def test_pipeline_without_target_repo(
        self, mock_config: OrchestratorConfig
    ) -> None:
        """Without target_repo, pipeline runs normally (no worktree)."""
        state = AppState(mock_config)

        task_id = "no-wt-01"
        await state.run_pipeline(task_id, "Simple task")

        pipeline = state.pipelines[task_id]
        assert pipeline.status.value == "completed"


class TestWorktreeMerge:
    """B: After successful pipeline, worktree merge is attempted."""

    async def test_merge_after_pipeline(
        self, tmp_path: Path, mock_config: OrchestratorConfig
    ) -> None:
        repo = _create_test_repo(tmp_path)
        state = AppState(mock_config)

        task_id = "merge-test-01"
        await state.run_pipeline(task_id, "Add greeting feature", target_repo=repo)

        # Pipeline should complete (merge is best-effort, no real file changes from mock)
        pipeline = state.pipelines[task_id]
        assert pipeline.status.value == "completed"

        # Completed event should exist
        completed_events = [
            e for e in state.event_bus.history if e.type.value == "pipeline.completed"
        ]
        assert len(completed_events) >= 1


class TestConcurrentPipelines:
    """C: Multiple pipelines run concurrently with task_id isolation."""

    async def test_two_concurrent_pipelines(
        self, mock_config: OrchestratorConfig
    ) -> None:
        state = AppState(mock_config)

        task1 = asyncio.create_task(
            state.run_pipeline("concurrent-1", "Build feature A")
        )
        task2 = asyncio.create_task(
            state.run_pipeline("concurrent-2", "Build feature B")
        )
        await asyncio.gather(task1, task2)

        assert state.pipelines["concurrent-1"].status.value == "completed"
        assert state.pipelines["concurrent-2"].status.value == "completed"
        assert len(state.pipelines["concurrent-1"].messages) == 3
        assert len(state.pipelines["concurrent-2"].messages) == 3

    async def test_concurrent_with_target_repos(
        self, tmp_path: Path, mock_config: OrchestratorConfig
    ) -> None:
        """Two pipelines targeting different repos concurrently."""
        repo1 = _create_test_repo(tmp_path / "r1")
        repo2 = _create_test_repo(tmp_path / "r2")
        state = AppState(mock_config)

        task1 = asyncio.create_task(
            state.run_pipeline("par-1", "Feature for repo1", target_repo=repo1)
        )
        task2 = asyncio.create_task(
            state.run_pipeline("par-2", "Feature for repo2", target_repo=repo2)
        )
        await asyncio.gather(task1, task2)

        assert state.pipelines["par-1"].status.value == "completed"
        assert state.pipelines["par-2"].status.value == "completed"

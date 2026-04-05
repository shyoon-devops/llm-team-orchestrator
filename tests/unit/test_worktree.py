"""Unit tests for WorktreeManager with real temporary git repos."""

import subprocess
from pathlib import Path

import pytest

from orchestrator.worktree.manager import WorktreeManager


def _init_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit at the given path."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", "main"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )
    # Configure user for commits inside this temporary repo
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )
    # Create initial commit so branches can be created
    readme = path / "README.md"
    readme.write_text("init")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _init_repo(tmp_path)
    return tmp_path


class TestCreateWorktree:
    async def test_create_worktree(self, repo: Path) -> None:
        mgr = WorktreeManager(str(repo))
        wt_path = await mgr.create("task1", "planner")

        # Verify the worktree directory exists
        assert Path(wt_path).is_dir()
        assert wt_path == f"{repo}/.worktrees/planner-task1"

        # Verify the branch exists
        result = subprocess.run(
            ["git", "branch", "--list", "agent/planner-task1"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "agent/planner-task1" in result.stdout


class TestCleanupWorktree:
    async def test_cleanup_worktree(self, repo: Path) -> None:
        mgr = WorktreeManager(str(repo))
        wt_path = await mgr.create("task2", "coder")

        assert Path(wt_path).is_dir()

        await mgr.cleanup("task2", "coder")

        # Verify path removed
        assert not Path(wt_path).exists()

        # Verify branch deleted
        result = subprocess.run(
            ["git", "branch", "--list", "agent/coder-task2"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "agent/coder-task2" not in result.stdout


class TestMergeToTarget:
    async def test_merge_to_target(self, repo: Path) -> None:
        mgr = WorktreeManager(str(repo))
        wt_path = await mgr.create("task3", "implementer")

        # Add a file in the worktree and commit
        new_file = Path(wt_path) / "new_feature.py"
        new_file.write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=wt_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add feature"],
            cwd=wt_path,
            check=True,
            capture_output=True,
        )

        # Merge into main
        success = await mgr.merge_to_target("task3", "implementer", "main")
        assert success is True

        # Verify the file exists on main
        assert (repo / "new_feature.py").is_file()


class TestListWorktrees:
    async def test_list_worktrees(self, repo: Path) -> None:
        mgr = WorktreeManager(str(repo))
        await mgr.create("task4", "planner")
        await mgr.create("task4", "reviewer")

        worktrees = await mgr.list_worktrees()
        branches = {wt["branch"] for wt in worktrees}

        assert "agent/planner-task4" in branches
        assert "agent/reviewer-task4" in branches
        assert len(worktrees) >= 2

        # Verify role extraction
        roles = {wt["role"] for wt in worktrees}
        assert "planner" in roles
        assert "reviewer" in roles


class TestCleanupAll:
    async def test_cleanup_all(self, repo: Path) -> None:
        mgr = WorktreeManager(str(repo))
        path_a = await mgr.create("task5", "planner")
        path_b = await mgr.create("task5", "coder")

        assert Path(path_a).is_dir()
        assert Path(path_b).is_dir()

        await mgr.cleanup_all("task5")

        assert not Path(path_a).exists()
        assert not Path(path_b).exists()

        # Branches should be gone
        result = subprocess.run(
            ["git", "branch"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert "agent/planner-task5" not in result.stdout
        assert "agent/coder-task5" not in result.stdout

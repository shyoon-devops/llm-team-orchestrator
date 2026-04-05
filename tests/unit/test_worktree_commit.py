"""Tests for V2 iter2: worktree commit + context chaining log."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.bus import EventBus
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.models import TaskItem
from orchestrator.core.queue.worker import AgentWorker


class StubExecutor(AgentExecutor):
    """Stub executor for tests."""

    executor_type: str = "mock"

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        return AgentResult(output="stub output", exit_code=0)

    async def health_check(self) -> bool:
        return True


async def test_commit_worktree_changes(tmp_path: Path) -> None:
    """Create a git repo, write a file, call _commit_worktree_changes, verify commit."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize git repo
    proc = await asyncio.create_subprocess_exec(
        "git", "init", cwd=str(repo_dir),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    for cmd in [
        ["git", "config", "user.name", "test"],
        ["git", "config", "user.email", "test@test.com"],
    ]:
        p = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(repo_dir),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await p.wait()

    # Initial commit
    (repo_dir / ".gitkeep").write_text("")
    for cmd in [
        ["git", "add", "-A"],
        ["git", "commit", "-m", "init"],
    ]:
        p = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(repo_dir),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await p.wait()

    # Write a new file (simulating agent output)
    (repo_dir / "hello.py").write_text("print('hello')\n")

    # Call _commit_worktree_changes
    engine = OrchestratorEngine()
    committed = await engine._commit_worktree_changes(str(repo_dir), "agent: test-branch")
    assert committed is True

    # Verify git log shows the commit
    proc = await asyncio.create_subprocess_exec(
        "git", "log", "--oneline", cwd=str(repo_dir),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    log_output = stdout.decode()
    assert "agent: test-branch" in log_output


async def test_commit_worktree_no_changes(tmp_path: Path) -> None:
    """When there are no changes, _commit_worktree_changes returns False."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize git repo with initial commit
    proc = await asyncio.create_subprocess_exec(
        "git", "init", cwd=str(repo_dir),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    for cmd in [
        ["git", "config", "user.name", "test"],
        ["git", "config", "user.email", "test@test.com"],
    ]:
        p = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(repo_dir),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await p.wait()

    (repo_dir / ".gitkeep").write_text("")
    for cmd in [
        ["git", "add", "-A"],
        ["git", "commit", "-m", "init"],
    ]:
        p = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(repo_dir),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await p.wait()

    # No new files — should return False
    engine = OrchestratorEngine()
    committed = await engine._commit_worktree_changes(str(repo_dir), "agent: no-op")
    assert committed is False


async def test_context_chaining_log() -> None:
    """Verify logger.info('context_chaining') is called when depends_on has results."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    # Set up dependency with result
    dep_task = TaskItem(
        id="dep-1",
        title="Architect task",
        description="Design the architecture",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(dep_task)
    claimed = await board.claim("architect", "worker-arch")
    assert claimed is not None
    await board.complete("dep-1", "JWT middleware design")

    # Create dependent task
    impl_task = TaskItem(
        id="t1",
        title="Implementer task",
        description="Implement features",
        lane="implementer",
        depends_on=["dep-1"],
        pipeline_id="pipe-1",
    )

    with patch("orchestrator.core.queue.worker.logger") as mock_logger:
        prompt = await worker._build_prompt(impl_task)

        # Verify the log was emitted
        mock_logger.info.assert_any_call(
            "context_chaining",
            task_id="t1",
            lane="implementer",
            depends_on=["dep-1"],
            context_length=len(prompt) - len("Implement features"),
        )


async def test_context_chaining_log_not_called_without_deps() -> None:
    """Verify context_chaining log is NOT emitted when no depends_on."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    task = TaskItem(
        id="t1",
        title="Task",
        description="Build features",
        lane="implementer",
        depends_on=[],
        pipeline_id="pipe-1",
    )

    with patch("orchestrator.core.queue.worker.logger") as mock_logger:
        await worker._build_prompt(task)

        # context_chaining should NOT be called
        calls = [
            c for c in mock_logger.info.call_args_list
            if c[0] and c[0][0] == "context_chaining"
        ]
        assert len(calls) == 0

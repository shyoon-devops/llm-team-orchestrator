"""WorktreeManager — Git worktree lifecycle management (stub for Phase 1)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from orchestrator.core.errors.exceptions import WorktreeCleanupError, WorktreeCreateError

logger = structlog.get_logger()


class WorktreeManager:
    """Git worktree 생성/정리/병합을 관리한다.

    Phase 1에서는 기본 구조만 제공한다.
    """

    def __init__(self, base_dir: str = "/tmp/orchestrator-worktrees") -> None:
        """
        Args:
            base_dir: worktree 생성 기본 디렉토리.
        """
        self._base_dir = Path(base_dir)

    async def create(
        self,
        repo_path: str,
        branch: str,
    ) -> Path:
        """Git worktree를 생성한다.

        Args:
            repo_path: 소스 Git 저장소 경로.
            branch: worktree 브랜치 이름.

        Returns:
            생성된 worktree 경로.

        Raises:
            WorktreeCreateError: 생성 실패.
        """
        worktree_path = self._base_dir / branch
        worktree_path.mkdir(parents=True, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "add",
            str(worktree_path),
            "-b",
            branch,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise WorktreeCreateError(
                f"Failed to create worktree: {stderr.decode()}",
                repo_path=repo_path,
                branch=branch,
            )

        logger.info(
            "worktree_created",
            repo_path=repo_path,
            branch=branch,
            path=str(worktree_path),
        )
        return worktree_path

    async def cleanup(self, repo_path: str, branch: str) -> None:
        """Git worktree를 정리한다.

        Args:
            repo_path: 소스 Git 저장소 경로.
            branch: 정리할 worktree 브랜치 이름.

        Raises:
            WorktreeCleanupError: 정리 실패.
        """
        worktree_path = self._base_dir / branch

        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "remove",
            str(worktree_path),
            "--force",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise WorktreeCleanupError(
                f"Failed to cleanup worktree: {stderr.decode()}",
                repo_path=repo_path,
                branch=branch,
            )

        logger.info("worktree_cleaned", branch=branch)

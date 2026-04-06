"""WorktreeManager — Git worktree lifecycle management."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from orchestrator.core.errors.exceptions import WorktreeCleanupError, WorktreeCreateError

logger = structlog.get_logger()


@dataclass
class _WorktreeInfo:
    """Internal record for a managed worktree."""

    branch: str
    path: str
    repo: str
    base_branch: str


class WorktreeManager:
    """Git worktree 생성/정리/병합을 관리한다.

    Spec (functions.md §7):
    - create(repo_path, branch_name, *, base_branch="main") -> str
    - cleanup(branch_name) -> None  (uses stored repo_path)
    - merge_to_target(branch_name, target_branch="main") -> bool
    - list_worktrees() -> list[dict[str, str]]
    """

    def __init__(self, base_dir: str = "/tmp/orchestrator-worktrees") -> None:
        """
        Args:
            base_dir: worktree 생성 기본 디렉토리.
        """
        self._base_dir = Path(base_dir)
        self._worktrees: dict[str, _WorktreeInfo] = {}

    async def create(
        self,
        repo_path: str,
        branch_name: str,
        *,
        base_branch: str | None = None,
    ) -> str:
        """Git worktree를 생성한다.

        Args:
            repo_path: 소스 Git 저장소 경로.
            branch_name: worktree 브랜치 이름.
            base_branch: 기반 브랜치. None이면 자동 감지 (HEAD).

        Returns:
            생성된 worktree 디렉토리 경로.

        Raises:
            WorktreeCreateError: 생성 실패.
            FileNotFoundError: repo_path가 존재하지 않는 경우.
        """
        worktree_path = self._base_dir / branch_name
        worktree_path.mkdir(parents=True, exist_ok=True)

        # base_branch 자동 감지 (None이면 HEAD 사용)
        if base_branch is None:
            detect_proc = await asyncio.create_subprocess_exec(
                "git", "symbolic-ref", "--short", "HEAD",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await detect_proc.communicate()
            base_branch = stdout.decode().strip() or "main"

        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            base_branch,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise WorktreeCreateError(
                f"Failed to create worktree: {stderr.decode()}",
                repo_path=repo_path,
                branch=branch_name,
            )

        # Register in internal mapping
        self._worktrees[branch_name] = _WorktreeInfo(
            branch=branch_name,
            path=str(worktree_path),
            repo=repo_path,
            base_branch=base_branch,
        )

        logger.info(
            "worktree_created",
            repo_path=repo_path,
            branch=branch_name,
            path=str(worktree_path),
        )
        return str(worktree_path)

    async def cleanup(self, branch_name: str) -> None:
        """Git worktree를 정리한다 (제거).

        Spec: uses stored repo_path from create() call.

        Args:
            branch_name: 정리할 worktree 브랜치 이름.

        Raises:
            KeyError: 등록되지 않은 브랜치 이름.
            WorktreeCleanupError: 정리 실패.
        """
        info = self._worktrees.get(branch_name)
        if info is None:
            msg = f"Unknown worktree branch: {branch_name}"
            raise KeyError(msg)

        worktree_path = info.path
        repo_path = info.repo

        proc = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "remove",
            worktree_path,
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
                branch=branch_name,
            )

        # Delete branch
        proc2 = await asyncio.create_subprocess_exec(
            "git",
            "branch",
            "-D",
            branch_name,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        del self._worktrees[branch_name]
        logger.info("worktree_cleaned", branch=branch_name)

    async def merge_to_target(
        self,
        branch_name: str,
        target_branch: str = "main",
    ) -> bool:
        """worktree 브랜치의 변경사항을 대상 브랜치에 merge한다.

        Spec: uses stored repo_path from create() call.

        Args:
            branch_name: merge할 worktree 브랜치 이름.
            target_branch: merge 대상 브랜치. 기본값 "main".

        Returns:
            merge 성공 시 True.

        Raises:
            KeyError: 등록되지 않은 브랜치 이름.
            WorktreeCleanupError: Git 명령 실패.
        """
        info = self._worktrees.get(branch_name)
        if info is None:
            msg = f"Unknown worktree branch: {branch_name}"
            raise KeyError(msg)

        repo_path = info.repo

        # Checkout target branch
        proc_co = await asyncio.create_subprocess_exec(
            "git",
            "checkout",
            target_branch,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc_co.communicate()

        # Merge with theirs strategy (later branch wins on conflict)
        proc = await asyncio.create_subprocess_exec(
            "git",
            "merge",
            branch_name,
            "--no-ff",
            "-X", "theirs",
            "-m",
            f"merge: {branch_name} into {target_branch}",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.warning(
                "worktree_merge_failed",
                branch=branch_name,
                target=target_branch,
                stderr=stderr.decode(),
            )
            return False

        logger.info(
            "worktree_merged",
            branch=branch_name,
            target=target_branch,
        )
        return True

    def list_worktrees(self) -> list[dict[str, str]]:
        """현재 관리 중인 worktree 목록을 반환한다.

        Returns:
            worktree 정보 목록. 각 항목:
            {"branch": str, "path": str, "repo": str, "base_branch": str}
        """
        return [
            {
                "branch": info.branch,
                "path": info.path,
                "repo": info.repo,
                "base_branch": info.base_branch,
            }
            for info in self._worktrees.values()
        ]

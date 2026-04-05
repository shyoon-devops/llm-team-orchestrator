"""FileDiffCollector — collects file changes in a worktree (stub for Phase 1)."""

from __future__ import annotations

import asyncio

import structlog

from orchestrator.core.models.pipeline import FileChange

logger = structlog.get_logger()


class FileDiffCollector:
    """worktree 파일 변경 수집기.

    에이전트 실행 전후 스냅샷을 비교하여 변경된 파일 목록을 생성한다.
    Phase 1에서는 기본 구조만 제공한다.
    """

    def __init__(self, worktree_path: str) -> None:
        """
        Args:
            worktree_path: worktree 경로.
        """
        self._worktree_path = worktree_path

    async def snapshot(self) -> None:
        """현재 파일 상태를 스냅샷한다."""
        logger.debug("snapshot_taken", path=self._worktree_path)

    async def collect_changes(self) -> list[FileChange]:
        """스냅샷 이후 변경된 파일 목록을 수집한다.

        Returns:
            변경된 파일 목록.
        """
        proc = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            "--name-status",
            "HEAD",
            cwd=self._worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if not stdout:
            return []

        changes: list[FileChange] = []
        for line in stdout.decode().strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status, path = parts
            if status == "A":
                change_type = "added"
            elif status == "D":
                change_type = "deleted"
            else:
                change_type = "modified"
            changes.append(FileChange(path=path, change_type=change_type))

        return changes

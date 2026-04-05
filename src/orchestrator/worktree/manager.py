"""Git worktree manager for agent isolation."""

import asyncio
import contextlib

import structlog

logger = structlog.get_logger(__name__)


class WorktreeError(Exception):
    """Error during worktree operation."""


class WorktreeManager:
    """Manages git worktrees so each agent runs in its own isolated branch."""

    def __init__(self, repo_path: str) -> None:
        """Initialize with the main git repository path."""
        self._repo_path = repo_path

    @staticmethod
    def _branch_name(task_id: str, role: str) -> str:
        return f"agent/{role}-{task_id}"

    def _worktree_path(self, task_id: str, role: str) -> str:
        return f"{self._repo_path}/.worktrees/{role}-{task_id}"

    async def _run_git(self, *args: str, cwd: str | None = None) -> str:
        """Run a git command and return stdout. Raises WorktreeError on failure."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd or self._repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = stderr.decode().strip()
            raise WorktreeError(f"git {' '.join(args)} failed: {msg}")
        return stdout.decode().strip()

    async def create(self, task_id: str, role: str) -> str:
        """Create a worktree for the given task/role.

        Branch name: agent/{role}-{task_id}
        Worktree path: {repo_path}/.worktrees/{role}-{task_id}
        Returns the worktree path.
        """
        branch = self._branch_name(task_id, role)
        path = self._worktree_path(task_id, role)

        await self._run_git("worktree", "add", path, "-b", branch)
        logger.info("worktree_created", branch=branch, path=path)
        return path

    async def cleanup(self, task_id: str, role: str) -> None:
        """Remove worktree and delete branch."""
        branch = self._branch_name(task_id, role)
        path = self._worktree_path(task_id, role)

        await self._run_git("worktree", "remove", path, "--force")
        await self._run_git("branch", "-D", branch)
        logger.info("worktree_cleaned", branch=branch, path=path)

    async def merge_to_target(self, task_id: str, role: str, target_branch: str = "main") -> bool:
        """Merge the worktree branch into target.

        Returns True on success, False on conflict.
        """
        branch = self._branch_name(task_id, role)

        await self._run_git("checkout", target_branch)
        try:
            await self._run_git("merge", "--no-ff", branch, "-m", f"merge {branch}")
            logger.info("worktree_merged", branch=branch, target=target_branch)
            return True
        except WorktreeError:
            # Abort the failed merge so the repo is left clean.
            with contextlib.suppress(WorktreeError):
                await self._run_git("merge", "--abort")
            logger.warning("worktree_merge_conflict", branch=branch, target=target_branch)
            return False

    async def list_worktrees(self) -> list[dict[str, str]]:
        """List active worktrees.

        Returns a list of dicts with keys: path, branch, role.
        Only includes worktrees created by this manager (branch prefix ``agent/``).
        """
        output = await self._run_git("worktree", "list", "--porcelain")
        worktrees: list[dict[str, str]] = []
        current_path: str | None = None
        current_branch: str | None = None

        for line in output.splitlines():
            if line.startswith("worktree "):
                current_path = line[len("worktree ") :]
            elif line.startswith("branch "):
                ref = line[len("branch ") :]
                # refs/heads/agent/role-taskid
                current_branch = ref.removeprefix("refs/heads/")
            elif line == "":
                if (
                    current_path is not None
                    and current_branch is not None
                    and current_branch.startswith("agent/")
                ):
                    # Extract role from branch: agent/{role}-{task_id}
                    suffix = current_branch[len("agent/") :]
                    role = suffix.rsplit("-", 1)[0] if "-" in suffix else suffix
                    worktrees.append({"path": current_path, "branch": current_branch, "role": role})
                current_path = None
                current_branch = None

        # Handle last entry if output doesn't end with blank line
        if (
            current_path is not None
            and current_branch is not None
            and current_branch.startswith("agent/")
        ):
            suffix = current_branch[len("agent/") :]
            role = suffix.rsplit("-", 1)[0] if "-" in suffix else suffix
            worktrees.append({"path": current_path, "branch": current_branch, "role": role})

        return worktrees

    async def cleanup_all(self, task_id: str) -> None:
        """Cleanup all worktrees for a given task_id."""
        worktrees = await self.list_worktrees()
        for wt in worktrees:
            branch = wt["branch"]
            # branch format: agent/{role}-{task_id}
            if branch.endswith(f"-{task_id}"):
                role = wt["role"]
                await self.cleanup(task_id, role)
                logger.info("worktree_cleanup_all_removed", branch=branch)

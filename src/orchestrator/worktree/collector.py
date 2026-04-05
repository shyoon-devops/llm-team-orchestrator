"""File diff collector — tracks files created/modified by CLI execution."""

import os

import structlog

logger = structlog.get_logger(__name__)


class FileDiffCollector:
    """Compares filesystem snapshots to detect created/modified/deleted files."""

    @staticmethod
    def snapshot(directory: str) -> dict[str, float]:
        """Take a snapshot of all files with their modification times.

        Returns ``{relative_path: mtime}``.
        Excludes the ``.git/`` directory.
        """
        result: dict[str, float] = {}
        for root, dirs, files in os.walk(directory):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != ".git"]
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, directory)
                result[rel] = os.path.getmtime(full)
        return result

    @staticmethod
    def diff(before: dict[str, float], after: dict[str, float]) -> dict[str, str]:
        """Compare two snapshots.

        Returns ``{relative_path: change_type}`` where *change_type* is
        ``"created"``, ``"modified"``, or ``"deleted"``.
        """
        changes: dict[str, str] = {}

        for path, mtime in after.items():
            if path not in before:
                changes[path] = "created"
            elif mtime != before[path]:
                changes[path] = "modified"

        for path in before:
            if path not in after:
                changes[path] = "deleted"

        return changes

    @staticmethod
    def collect_changes(directory: str, changes: dict[str, str]) -> dict[str, str]:
        """Read the content of changed files (created/modified only).

        Returns ``{relative_path: content}``.
        Skips binary files (records them as ``"[binary]"``).
        """
        result: dict[str, str] = {}
        for rel_path, change_type in changes.items():
            if change_type == "deleted":
                continue
            full = os.path.join(directory, rel_path)
            try:
                with open(full, encoding="utf-8") as f:
                    result[rel_path] = f.read()
            except UnicodeDecodeError:
                result[rel_path] = "[binary]"
            except OSError:
                logger.warning("collect_changes_read_error", path=rel_path)
        return result

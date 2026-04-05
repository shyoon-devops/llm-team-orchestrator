"""Unit tests for FileDiffCollector."""

import time
from pathlib import Path

import pytest

from orchestrator.worktree.collector import FileDiffCollector


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    return tmp_path


class TestSnapshot:
    def test_snapshot(self, workdir: Path) -> None:
        (workdir / "a.py").write_text("hello")
        (workdir / "b.txt").write_text("world")
        sub = workdir / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("nested")

        snap = FileDiffCollector.snapshot(str(workdir))

        assert "a.py" in snap
        assert "b.txt" in snap
        assert str(Path("sub") / "c.py") in snap
        assert len(snap) == 3

    def test_snapshot_excludes_git(self, workdir: Path) -> None:
        (workdir / ".git").mkdir()
        (workdir / ".git" / "config").write_text("gitconfig")
        (workdir / "real.py").write_text("code")

        snap = FileDiffCollector.snapshot(str(workdir))

        assert "real.py" in snap
        assert ".git/config" not in snap


class TestDiffCreated:
    def test_diff_created(self, workdir: Path) -> None:
        (workdir / "a.py").write_text("hello")
        before = FileDiffCollector.snapshot(str(workdir))

        (workdir / "b.py").write_text("new file")
        after = FileDiffCollector.snapshot(str(workdir))

        changes = FileDiffCollector.diff(before, after)
        assert changes["b.py"] == "created"
        assert "a.py" not in changes


class TestDiffModified:
    def test_diff_modified(self, workdir: Path) -> None:
        f = workdir / "a.py"
        f.write_text("original")
        before = FileDiffCollector.snapshot(str(workdir))

        # Ensure different mtime
        time.sleep(0.05)
        f.write_text("modified content")
        after = FileDiffCollector.snapshot(str(workdir))

        changes = FileDiffCollector.diff(before, after)
        assert changes["a.py"] == "modified"


class TestDiffDeleted:
    def test_diff_deleted(self, workdir: Path) -> None:
        f = workdir / "a.py"
        f.write_text("will be deleted")
        before = FileDiffCollector.snapshot(str(workdir))

        f.unlink()
        after = FileDiffCollector.snapshot(str(workdir))

        changes = FileDiffCollector.diff(before, after)
        assert changes["a.py"] == "deleted"


class TestCollectChanges:
    def test_collect_changes(self, workdir: Path) -> None:
        (workdir / "new.py").write_text("print('hello')")
        (workdir / "mod.py").write_text("updated content")

        changes = {"new.py": "created", "mod.py": "modified", "gone.py": "deleted"}
        collected = FileDiffCollector.collect_changes(str(workdir), changes)

        assert collected["new.py"] == "print('hello')"
        assert collected["mod.py"] == "updated content"
        assert "gone.py" not in collected

    def test_collect_changes_binary(self, workdir: Path) -> None:
        binfile = workdir / "image.bin"
        binfile.write_bytes(b"\x00\x01\x02\xff\xfe")

        changes = {"image.bin": "created"}
        collected = FileDiffCollector.collect_changes(str(workdir), changes)

        assert collected["image.bin"] == "[binary]"

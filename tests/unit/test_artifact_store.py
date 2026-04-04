"""Unit tests for artifact store."""

import pytest

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.errors.exceptions import ContextError


@pytest.fixture
def store(tmp_path: object) -> ArtifactStore:
    return ArtifactStore(str(tmp_path))


class TestArtifactStore:
    def test_save_and_load(self, store: ArtifactStore) -> None:
        store.save("test.txt", "hello world")
        assert store.load("test.txt") == "hello world"

    def test_load_nonexistent(self, store: ArtifactStore) -> None:
        with pytest.raises(ContextError, match="not found"):
            store.load("missing.txt")

    def test_exists(self, store: ArtifactStore) -> None:
        assert store.exists("test.txt") is False
        store.save("test.txt", "content")
        assert store.exists("test.txt") is True

    def test_save_with_metadata(self, store: ArtifactStore) -> None:
        store.save("plan.md", "plan content", metadata={"provider": "mock", "tokens": 100})
        meta = store.load_metadata("plan.md")
        assert meta["provider"] == "mock"
        assert meta["tokens"] == 100

    def test_load_metadata_missing(self, store: ArtifactStore) -> None:
        store.save("no_meta.txt", "content")
        assert store.load_metadata("no_meta.txt") == {}

    def test_list_artifacts(self, store: ArtifactStore) -> None:
        store.save("a.txt", "aaa")
        store.save("b.txt", "bbb")
        artifacts = store.list_artifacts()
        assert "a.txt" in artifacts
        assert "b.txt" in artifacts

    def test_list_excludes_metadata(self, store: ArtifactStore) -> None:
        store.save("doc.md", "content", metadata={"key": "val"})
        artifacts = store.list_artifacts()
        assert "doc.md" in artifacts
        assert "doc.md.meta.json" not in artifacts

    def test_delete(self, store: ArtifactStore) -> None:
        store.save("to_delete.txt", "bye", metadata={"x": 1})
        store.delete("to_delete.txt")
        assert store.exists("to_delete.txt") is False

    def test_nested_path(self, store: ArtifactStore) -> None:
        store.save("sub/dir/file.txt", "nested")
        assert store.load("sub/dir/file.txt") == "nested"

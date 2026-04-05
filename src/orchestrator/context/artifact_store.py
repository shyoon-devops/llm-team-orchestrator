"""File-based artifact store for inter-agent context sharing."""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.errors.exceptions import ContextError


class ArtifactStore:
    """File-system based artifact store for sharing context between agents."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_dir(self, task_id: str | None) -> Path:
        """Return base_dir or a task-scoped subdirectory."""
        if task_id:
            d = self.base_dir / task_id
            d.mkdir(parents=True, exist_ok=True)
            return d
        return self.base_dir

    def save(
        self,
        key: str,
        content: str,
        *,
        metadata: dict[str, object] | None = None,
        task_id: str | None = None,
    ) -> Path:
        """Save an artifact and return its path."""
        base = self._resolve_dir(task_id)
        artifact_path = base / key
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")

        if metadata is not None:
            meta_path = base / f"{key}.meta.json"
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

        return artifact_path

    def load(self, key: str, *, task_id: str | None = None) -> str:
        """Load an artifact by key."""
        base = self._resolve_dir(task_id)
        artifact_path = base / key
        if not artifact_path.exists():
            raise ContextError(f"Artifact not found: {key}")
        return artifact_path.read_text(encoding="utf-8")

    def load_metadata(self, key: str, *, task_id: str | None = None) -> dict[str, object]:
        """Load metadata for an artifact."""
        base = self._resolve_dir(task_id)
        meta_path = base / f"{key}.meta.json"
        if not meta_path.exists():
            return {}
        return json.loads(meta_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def exists(self, key: str, *, task_id: str | None = None) -> bool:
        """Check if an artifact exists."""
        base = self._resolve_dir(task_id)
        return (base / key).exists()

    def list_artifacts(self, *, task_id: str | None = None) -> list[str]:
        """List all artifact keys."""
        base = self._resolve_dir(task_id)
        return [
            str(p.relative_to(base))
            for p in base.rglob("*")
            if p.is_file() and not p.name.endswith(".meta.json")
        ]

    def delete(self, key: str, *, task_id: str | None = None) -> None:
        """Delete an artifact and its metadata."""
        base = self._resolve_dir(task_id)
        artifact_path = base / key
        if artifact_path.exists():
            artifact_path.unlink()
        meta_path = base / f"{key}.meta.json"
        if meta_path.exists():
            meta_path.unlink()

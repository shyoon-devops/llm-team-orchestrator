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

    def save(self, key: str, content: str, *, metadata: dict[str, object] | None = None) -> Path:
        """Save an artifact and return its path."""
        artifact_path = self.base_dir / key
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")

        if metadata is not None:
            meta_path = self.base_dir / f"{key}.meta.json"
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

        return artifact_path

    def load(self, key: str) -> str:
        """Load an artifact by key."""
        artifact_path = self.base_dir / key
        if not artifact_path.exists():
            raise ContextError(f"Artifact not found: {key}")
        return artifact_path.read_text(encoding="utf-8")

    def load_metadata(self, key: str) -> dict[str, object]:
        """Load metadata for an artifact."""
        meta_path = self.base_dir / f"{key}.meta.json"
        if not meta_path.exists():
            return {}
        return json.loads(meta_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def exists(self, key: str) -> bool:
        """Check if an artifact exists."""
        return (self.base_dir / key).exists()

    def list_artifacts(self) -> list[str]:
        """List all artifact keys."""
        return [
            str(p.relative_to(self.base_dir))
            for p in self.base_dir.rglob("*")
            if p.is_file() and not p.name.endswith(".meta.json")
        ]

    def delete(self, key: str) -> None:
        """Delete an artifact and its metadata."""
        artifact_path = self.base_dir / key
        if artifact_path.exists():
            artifact_path.unlink()
        meta_path = self.base_dir / f"{key}.meta.json"
        if meta_path.exists():
            meta_path.unlink()

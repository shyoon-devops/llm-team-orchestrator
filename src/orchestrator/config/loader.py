"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.config.schema import OrchestratorConfig


def load_config(path: str | Path) -> OrchestratorConfig:
    """Load and validate YAML configuration."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Support both flat and nested formats
    if "orchestrator" in raw:
        data = raw["orchestrator"]
        # Merge top-level agents/tasks into orchestrator section
        if "agents" in raw and "agents" not in data:
            data["agents"] = raw["agents"]
        if "tasks" in raw and "tasks" not in data:
            data["tasks"] = raw["tasks"]
    else:
        data = raw

    return OrchestratorConfig.model_validate(data)


def load_config_with_defaults(path: str | Path | None = None) -> OrchestratorConfig:
    """Load config from path, or return defaults if no path given."""
    if path is None:
        # Try default locations
        for candidate in ["team-config.yaml", "team-config.yml"]:
            if Path(candidate).exists():
                return load_config(candidate)
        return OrchestratorConfig()
    return load_config(path)

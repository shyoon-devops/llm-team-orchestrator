"""Unit tests for YAML configuration loader."""

from pathlib import Path

import pytest

from orchestrator.config.loader import load_config, load_config_with_defaults
from orchestrator.config.schema import OrchestratorConfig


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    config = tmp_path / "team-config.yaml"
    config.write_text(
        """
orchestrator:
  max_parallel_agents: 3
  timeout_per_task: 300
  log_level: debug
  dashboard:
    enabled: true
    port: 8080

agents:
  planner:
    cli: claude
    role: architect
    timeout: 200
  coder:
    cli: codex
    role: implementer

tasks:
  design:
    description: Design the API
    agent: planner
    priority: 1
  build:
    description: Build the API
    agent: coder
    depends_on: [design]
    priority: 2
""",
        encoding="utf-8",
    )
    return config


class TestConfigLoader:
    def test_load_config(self, config_file: Path) -> None:
        config = load_config(config_file)
        assert config.max_parallel_agents == 3
        assert config.timeout_per_task == 300
        assert config.log_level == "debug"
        assert config.dashboard.port == 8080

    def test_load_agents(self, config_file: Path) -> None:
        config = load_config(config_file)
        assert "planner" in config.agents
        assert config.agents["planner"].cli == "claude"
        assert config.agents["planner"].timeout == 200

    def test_load_tasks(self, config_file: Path) -> None:
        config = load_config(config_file)
        assert "design" in config.tasks
        assert config.tasks["build"].depends_on == ["design"]

    def test_load_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_defaults(self) -> None:
        config = OrchestratorConfig()
        assert config.max_parallel_agents == 4
        assert config.dashboard.enabled is True
        assert config.dashboard.port == 3000

    def test_load_with_defaults_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = load_config_with_defaults()
        assert config.max_parallel_agents == 4  # defaults

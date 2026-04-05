"""Tests for PresetRegistry — load, list, merge, save, search paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.core.presets.models import (
    AgentPreset,
    PersonaDef,
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)
from orchestrator.core.presets.registry import PresetRegistry, _deep_merge


@pytest.fixture
def presets_dir(tmp_path: Path) -> Path:
    """Create a temporary presets directory with agents/ and teams/ subdirs."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    teams_dir = tmp_path / "teams"
    teams_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_agent_yaml(presets_dir: Path) -> Path:
    """Write a sample agent preset YAML file."""
    yaml_content = """\
name: test-agent
description: "Test agent"
persona:
  role: "Test Developer"
  goal: "Write test code"
  backstory: "Experienced tester"
  constraints:
    - "Write tests"
execution:
  mode: cli
  preferred_cli: claude
  fallback_cli: codex
tags:
  - testing
limits:
  timeout: 120
  max_turns: 30
"""
    path = presets_dir / "agents" / "test-agent.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    return path


@pytest.fixture
def sample_team_yaml(presets_dir: Path) -> Path:
    """Write a sample team preset YAML file."""
    yaml_content = """\
name: test-team
description: "Test team"
agents:
  dev:
    preset: test-agent
tasks:
  code:
    description: "Write code"
    agent: dev
workflow: sequential
synthesis_strategy: narrative
"""
    path = presets_dir / "teams" / "test-team.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    return path


class TestPresetRegistryInit:
    def test_empty_directory(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        assert registry.list_agent_presets() == []
        assert registry.list_team_presets() == []

    def test_nonexistent_directory(self, tmp_path: Path):
        registry = PresetRegistry([str(tmp_path / "nonexistent")])
        assert registry.list_agent_presets() == []

    def test_scan_agent_yaml(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        presets = registry.list_agent_presets()
        assert len(presets) == 1
        assert presets[0].name == "test-agent"
        assert presets[0].persona.role == "Test Developer"

    def test_scan_team_yaml(self, presets_dir: Path, sample_team_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        presets = registry.list_team_presets()
        assert len(presets) == 1
        assert presets[0].name == "test-team"

    def test_scan_multiple_directories(self, tmp_path: Path):
        dir1 = tmp_path / "dir1" / "agents"
        dir1.mkdir(parents=True)
        dir2 = tmp_path / "dir2" / "agents"
        dir2.mkdir(parents=True)

        yaml1 = """\
name: agent-a
persona:
  role: "Agent A"
  goal: "Goal A"
"""
        yaml2 = """\
name: agent-b
persona:
  role: "Agent B"
  goal: "Goal B"
"""
        (dir1 / "agent-a.yaml").write_text(yaml1, encoding="utf-8")
        (dir2 / "agent-b.yaml").write_text(yaml2, encoding="utf-8")

        registry = PresetRegistry([str(tmp_path / "dir1"), str(tmp_path / "dir2")])
        presets = registry.list_agent_presets()
        names = [p.name for p in presets]
        assert "agent-a" in names
        assert "agent-b" in names


class TestPresetRegistryLoad:
    def test_load_agent_preset(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = registry.load_agent_preset("test-agent")
        assert preset.name == "test-agent"
        assert preset.persona.goal == "Write test code"

    def test_load_agent_preset_not_found(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        with pytest.raises(KeyError, match="Agent preset not found"):
            registry.load_agent_preset("nonexistent")

    def test_load_team_preset(self, presets_dir: Path, sample_team_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = registry.load_team_preset("test-team")
        assert preset.name == "test-team"
        assert preset.workflow == "sequential"

    def test_load_team_preset_not_found(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        with pytest.raises(KeyError, match="Team preset not found"):
            registry.load_team_preset("nonexistent")


class TestPresetRegistryList:
    def test_list_agent_presets_sorted(self, presets_dir: Path):
        for name in ["charlie", "alpha", "bravo"]:
            yaml_content = f"""\
name: {name}
persona:
  role: "{name}"
  goal: "Goal"
"""
            (presets_dir / "agents" / f"{name}.yaml").write_text(yaml_content, encoding="utf-8")

        registry = PresetRegistry([str(presets_dir)])
        presets = registry.list_agent_presets()
        names = [p.name for p in presets]
        assert names == ["alpha", "bravo", "charlie"]

    def test_list_team_presets_sorted(self, presets_dir: Path):
        for name in ["z-team", "a-team"]:
            yaml_content = f"""\
name: {name}
agents:
  dev:
    preset: implementer
tasks:
  work:
    description: "Work"
    agent: dev
"""
            (presets_dir / "teams" / f"{name}.yaml").write_text(yaml_content, encoding="utf-8")

        registry = PresetRegistry([str(presets_dir)])
        presets = registry.list_team_presets()
        names = [p.name for p in presets]
        assert names == ["a-team", "z-team"]


class TestPresetRegistrySave:
    def test_save_agent_preset(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = AgentPreset(
            name="new-agent",
            persona=PersonaDef(role="New", goal="Create"),
        )
        registry.save_agent_preset(preset)
        assert registry.load_agent_preset("new-agent").name == "new-agent"
        # Verify YAML file was written
        assert (presets_dir / "agents" / "new-agent.yaml").exists()

    def test_save_agent_preset_no_overwrite(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = AgentPreset(
            name="dup-agent",
            persona=PersonaDef(role="Dup", goal="Dup"),
        )
        registry.save_agent_preset(preset)
        with pytest.raises(ValueError, match="already exists"):
            registry.save_agent_preset(preset, overwrite=False)

    def test_save_team_preset(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = TeamPreset(
            name="new-team",
            agents={"dev": TeamAgentDef(preset="implementer")},
            tasks={"work": TeamTaskDef(description="Work", agent="dev")},
        )
        registry.save_team_preset(preset)
        assert registry.load_team_preset("new-team").name == "new-team"
        assert (presets_dir / "teams" / "new-team.yaml").exists()

    def test_save_team_preset_no_overwrite(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        preset = TeamPreset(
            name="dup-team",
            agents={"dev": TeamAgentDef(preset="implementer")},
            tasks={"work": TeamTaskDef(description="Work", agent="dev")},
        )
        registry.save_team_preset(preset)
        with pytest.raises(ValueError, match="already exists"):
            registry.save_team_preset(preset, overwrite=False)


class TestPresetRegistryMerge:
    def test_merge_scalar_override(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        merged = registry.merge_preset_with_overrides(
            "test-agent",
            {"model": "o3-mini"},
        )
        assert merged.model == "o3-mini"
        assert merged.persona.role == "Test Developer"  # preserved

    def test_merge_nested_override(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        merged = registry.merge_preset_with_overrides(
            "test-agent",
            {"limits": {"timeout": 600}},
        )
        assert merged.limits.timeout == 600
        assert merged.limits.max_turns == 30  # preserved from YAML

    def test_merge_list_replacement(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        merged = registry.merge_preset_with_overrides(
            "test-agent",
            {"persona": {"constraints": ["New constraint"]}},
        )
        assert merged.persona.constraints == ["New constraint"]

    def test_merge_preserves_original(self, presets_dir: Path, sample_agent_yaml: Path):
        registry = PresetRegistry([str(presets_dir)])
        original = registry.load_agent_preset("test-agent")
        registry.merge_preset_with_overrides(
            "test-agent",
            {"model": "o3-mini"},
        )
        assert original.model is None  # unchanged

    def test_merge_nonexistent_raises(self, presets_dir: Path):
        registry = PresetRegistry([str(presets_dir)])
        with pytest.raises(KeyError):
            registry.merge_preset_with_overrides("nonexistent", {})


class TestDeepMerge:
    def test_scalar_override(self):
        result = _deep_merge({"a": 1, "b": 2}, {"b": 3})
        assert result == {"a": 1, "b": 3}

    def test_nested_dict_merge(self):
        result = _deep_merge(
            {"nested": {"a": 1, "b": 2}},
            {"nested": {"b": 3}},
        )
        assert result == {"nested": {"a": 1, "b": 3}}

    def test_list_replacement(self):
        result = _deep_merge(
            {"items": [1, 2, 3]},
            {"items": [4, 5]},
        )
        assert result == {"items": [4, 5]}

    def test_new_key_addition(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_empty_override(self):
        result = _deep_merge({"a": 1}, {})
        assert result == {"a": 1}


class TestSearchPathPriority:
    def test_first_path_wins(self, tmp_path: Path):
        dir1 = tmp_path / "dir1" / "agents"
        dir1.mkdir(parents=True)
        dir2 = tmp_path / "dir2" / "agents"
        dir2.mkdir(parents=True)

        yaml1 = """\
name: same-name
persona:
  role: "From dir1"
  goal: "Goal 1"
"""
        yaml2 = """\
name: same-name
persona:
  role: "From dir2"
  goal: "Goal 2"
"""
        (dir1 / "same-name.yaml").write_text(yaml1, encoding="utf-8")
        (dir2 / "same-name.yaml").write_text(yaml2, encoding="utf-8")

        registry = PresetRegistry([str(tmp_path / "dir1"), str(tmp_path / "dir2")])
        preset = registry.load_agent_preset("same-name")
        assert preset.persona.role == "From dir1"  # first path wins

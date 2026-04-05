"""Tests for TeamPlanner — plan_team with preset, plan_team auto."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.core.planner.team_planner import TeamPlanner
from orchestrator.core.presets.models import (
    AgentPreset,
    PersonaDef,
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)
from orchestrator.core.presets.registry import PresetRegistry


@pytest.fixture
def registry_with_presets(tmp_path: Path) -> PresetRegistry:
    """Create a registry with test presets loaded."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    teams_dir = tmp_path / "teams"
    teams_dir.mkdir()

    registry = PresetRegistry([str(tmp_path)])

    # Register agent presets directly
    registry.save_agent_preset(
        AgentPreset(
            name="architect",
            persona=PersonaDef(role="Architect", goal="Design systems"),
            preferred_cli="claude",
        )
    )
    registry.save_agent_preset(
        AgentPreset(
            name="implementer",
            persona=PersonaDef(role="Developer", goal="Write code"),
            preferred_cli="codex",
        )
    )
    registry.save_agent_preset(
        AgentPreset(
            name="reviewer",
            persona=PersonaDef(role="Reviewer", goal="Review code"),
            preferred_cli="claude",
        )
    )
    return registry


@pytest.fixture
def team_preset() -> TeamPreset:
    """Create a sample team preset."""
    return TeamPreset(
        name="test-team",
        description="Test team",
        agents={
            "arch": TeamAgentDef(preset="architect"),
            "dev": TeamAgentDef(preset="implementer"),
            "rev": TeamAgentDef(preset="reviewer"),
        },
        tasks={
            "design": TeamTaskDef(
                description="Design the system",
                agent="arch",
            ),
            "implement": TeamTaskDef(
                description="Implement the code",
                agent="dev",
                depends_on=["design"],
            ),
            "review": TeamTaskDef(
                description="Review the code",
                agent="rev",
                depends_on=["implement"],
            ),
        },
        workflow="dag",
    )


class TestTeamPlannerPreset:
    async def test_plan_from_preset_subtask_count(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, preset = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        assert len(subtasks) == 3
        assert preset.name == "test-team"

    async def test_plan_from_preset_descriptions(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, _ = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        descriptions = [s.description for s in subtasks]
        assert any("Design the system" in d for d in descriptions)
        assert any("Implement the code" in d for d in descriptions)
        assert any("Review the code" in d for d in descriptions)
        # 사용자 태스크도 포함되어야 함
        assert all("Build auth system" in d for d in descriptions)

    async def test_plan_from_preset_assigned_presets(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, _ = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        preset_names = {s.assigned_preset for s in subtasks}
        assert preset_names == {"arch", "dev", "rev"}

    async def test_plan_from_preset_cli_resolution(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, _ = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        cli_map = {s.assigned_preset: s.assigned_cli for s in subtasks}
        assert cli_map["arch"] == "claude"
        assert cli_map["dev"] == "codex"
        assert cli_map["rev"] == "claude"

    async def test_plan_from_preset_depends_on_mapping(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, _ = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        id_map = {s.assigned_preset: s.id for s in subtasks}

        # Find subtasks by assigned_preset
        impl_subtask = next(s for s in subtasks if s.assigned_preset == "dev")
        review_subtask = next(s for s in subtasks if s.assigned_preset == "rev")

        # implement depends on design
        assert id_map["arch"] in impl_subtask.depends_on
        # review depends on implement
        assert id_map["dev"] in review_subtask.depends_on

    async def test_plan_from_preset_unique_ids(self, registry_with_presets, team_preset):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        subtasks, _ = await planner.plan_team(
            "Build auth system",
            team_preset=team_preset,
        )
        ids = [s.id for s in subtasks]
        assert len(ids) == len(set(ids))  # All unique


class TestTeamPlannerAuto:
    async def test_plan_auto_returns_default_team(self):
        planner = TeamPlanner()
        subtasks, preset = await planner.plan_team("Implement JWT auth")
        assert len(subtasks) == 1
        assert preset.name == "auto-generated"

    async def test_plan_auto_subtask_description(self):
        planner = TeamPlanner()
        subtasks, _ = await planner.plan_team("Build login system")
        assert subtasks[0].description == "Build login system"

    async def test_plan_auto_assigned_preset(self):
        planner = TeamPlanner()
        subtasks, _ = await planner.plan_team("Build login system")
        assert subtasks[0].assigned_preset == "implementer"

    async def test_plan_auto_assigned_cli(self):
        planner = TeamPlanner()
        subtasks, _ = await planner.plan_team("Build login system")
        assert subtasks[0].assigned_cli == "codex"

    async def test_plan_auto_with_target_repo(self):
        planner = TeamPlanner()
        subtasks, _preset = await planner.plan_team(
            "Refactor utils",
            target_repo="/tmp/repo",
        )
        assert len(subtasks) == 1


class TestTeamPlannerValidation:
    async def test_empty_task_raises(self):
        planner = TeamPlanner()
        with pytest.raises(ValueError, match="empty"):
            await planner.plan_team("")

    async def test_whitespace_task_raises(self):
        planner = TeamPlanner()
        with pytest.raises(ValueError, match="empty"):
            await planner.plan_team("   ")


class TestTeamPlannerCLIResolution:
    async def test_resolve_cli_with_overrides(self, registry_with_presets):
        planner = TeamPlanner(preset_registry=registry_with_presets)
        team_preset = TeamPreset(
            name="override-team",
            agents={
                "dev": TeamAgentDef(
                    preset="implementer",
                    overrides={"preferred_cli": "gemini"},
                ),
            },
            tasks={
                "work": TeamTaskDef(
                    description="Work",
                    agent="dev",
                ),
            },
        )
        subtasks, _ = await planner.plan_team(
            "Build feature",
            team_preset=team_preset,
        )
        assert subtasks[0].assigned_cli == "gemini"

    async def test_resolve_cli_without_registry(self):
        planner = TeamPlanner(preset_registry=None)
        team_preset = TeamPreset(
            name="no-registry-team",
            agents={
                "dev": TeamAgentDef(preset="implementer"),
            },
            tasks={
                "work": TeamTaskDef(description="Work", agent="dev"),
            },
        )
        subtasks, _ = await planner.plan_team(
            "Build feature",
            team_preset=team_preset,
        )
        assert subtasks[0].assigned_cli is None

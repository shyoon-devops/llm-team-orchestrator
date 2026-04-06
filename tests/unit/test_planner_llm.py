"""Tests for TeamPlanner LLM-based role-specific instruction generation (CLI subprocess)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    return registry


@pytest.fixture
def team_preset() -> TeamPreset:
    """Create a team preset with design + implement tasks."""
    return TeamPreset(
        name="test-team",
        description="Test team",
        agents={
            "arch": TeamAgentDef(preset="architect"),
            "dev": TeamAgentDef(preset="implementer"),
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
        },
        workflow="dag",
    )


def _mock_cli_process(stdout_text: str, returncode: int = 0):
    """Create a mock subprocess that returns given stdout."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(
        return_value=(stdout_text.encode(), b"")
    )
    return proc


class TestTeamPlannerLLM:
    """CLI subprocess 기반 역할별 세부 지시 테스트."""

    async def test_use_llm_false_skips_cli(self, registry_with_presets, team_preset):
        """use_llm=False일 때 CLI를 호출하지 않는다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=False,
        )
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            subtasks, _ = await planner.plan_team(
                "Build auth system",
                team_preset=team_preset,
            )
            mock_exec.assert_not_called()
        assert any("Design the system" in s.description for s in subtasks)

    async def test_use_llm_true_calls_cli(self, registry_with_presets, team_preset):
        """use_llm=True일 때 claude CLI를 subprocess로 호출한다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        cli_output = (
            '```json\n'
            '[\n'
            '  {"role": "design", "instruction": "FastAPI 서버 아키텍처를 설계하세요"},\n'
            '  {"role": "implement", "instruction": "FastAPI 서버를 구현하세요"}\n'
            ']\n'
            '```'
        )

        mock_proc = _mock_cli_process(cli_output)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, preset = await planner.plan_team(
                "FastAPI 서버 구현",
                team_preset=team_preset,
            )

        assert len(subtasks) == 2
        assert preset.name == "test-team"
        design_sub = next(s for s in subtasks if s.assigned_preset == "arch")
        assert "FastAPI 서버 아키텍처를 설계하세요" in design_sub.description
        assert "FastAPI 서버 구현" in design_sub.description

    async def test_llm_fallback_on_cli_error(self, registry_with_presets, team_preset):
        """CLI 호출 실패 시 프리셋 기반으로 폴백한다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        mock_proc = _mock_cli_process("", returncode=1)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build auth system",
                team_preset=team_preset,
            )

        assert len(subtasks) == 2
        assert any("Design the system" in s.description for s in subtasks)

    async def test_llm_fallback_on_timeout(self, registry_with_presets, team_preset):
        """CLI 타임아웃 시 프리셋 기반으로 폴백한다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build auth system",
                team_preset=team_preset,
            )

        assert len(subtasks) == 2
        assert any("Design the system" in s.description for s in subtasks)

    async def test_llm_partial_roles(self, registry_with_presets, team_preset):
        """CLI가 일부 역할만 반환하면 나머지는 프리셋 폴백."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        cli_output = (
            '```json\n'
            '[{"role": "design", "instruction": "아키텍처 설계 상세 지시"}]\n'
            '```'
        )

        mock_proc = _mock_cli_process(cli_output)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build feature",
                team_preset=team_preset,
            )

        design_sub = next(s for s in subtasks if s.assigned_preset == "arch")
        impl_sub = next(s for s in subtasks if s.assigned_preset == "dev")

        assert "아키텍처 설계 상세 지시" in design_sub.description
        assert "Implement the code" in impl_sub.description

    async def test_llm_invalid_json_fallback(self, registry_with_presets, team_preset):
        """CLI가 유효하지 않은 JSON을 반환하면 프리셋 폴백."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        mock_proc = _mock_cli_process("This is not JSON at all")
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build feature",
                team_preset=team_preset,
            )

        assert len(subtasks) == 2
        assert any("Design the system" in s.description for s in subtasks)

    async def test_llm_preserves_depends_on(self, registry_with_presets, team_preset):
        """CLI 모드에서도 depends_on 매핑이 정확하다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        cli_output = (
            '```json\n'
            '[{"role": "design", "instruction": "설계"}, {"role": "implement", "instruction": "구현"}]\n'
            '```'
        )

        mock_proc = _mock_cli_process(cli_output)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build feature",
                team_preset=team_preset,
            )

        id_map = {s.assigned_preset: s.id for s in subtasks}
        impl_sub = next(s for s in subtasks if s.assigned_preset == "dev")
        assert id_map["arch"] in impl_sub.depends_on

    async def test_llm_preserves_cli_assignment(self, registry_with_presets, team_preset):
        """CLI 모드에서도 CLI 할당이 유지된다."""
        planner = TeamPlanner(
            preset_registry=registry_with_presets,
            use_llm=True,
        )

        cli_output = (
            '```json\n'
            '[{"role": "design", "instruction": "설계"}, {"role": "implement", "instruction": "구현"}]\n'
            '```'
        )

        mock_proc = _mock_cli_process(cli_output)
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            subtasks, _ = await planner.plan_team(
                "Build feature",
                team_preset=team_preset,
            )

        cli_map = {s.assigned_preset: s.assigned_cli for s in subtasks}
        assert cli_map["arch"] == "claude"
        assert cli_map["dev"] == "codex"


class TestParseLLMInstructions:
    """_parse_llm_instructions 파싱 로직 테스트."""

    def test_parse_valid_json_block(self, team_preset):
        planner = TeamPlanner()
        raw = '```json\n[{"role": "design", "instruction": "test"}]\n```'
        result = planner._parse_llm_instructions(raw, team_preset)
        assert result == {"design": "test"}

    def test_parse_bare_json(self, team_preset):
        planner = TeamPlanner()
        raw = '[{"role": "design", "instruction": "test"}]'
        result = planner._parse_llm_instructions(raw, team_preset)
        assert result == {"design": "test"}

    def test_parse_invalid_json(self, team_preset):
        planner = TeamPlanner()
        raw = "not json"
        result = planner._parse_llm_instructions(raw, team_preset)
        assert result == {}

    def test_parse_filters_invalid_roles(self, team_preset):
        planner = TeamPlanner()
        raw = '[{"role": "design", "instruction": "ok"}, {"role": "fake", "instruction": "skip"}]'
        result = planner._parse_llm_instructions(raw, team_preset)
        assert "design" in result
        assert "fake" not in result

    def test_parse_empty_instruction_skipped(self, team_preset):
        planner = TeamPlanner()
        raw = '[{"role": "design", "instruction": ""}]'
        result = planner._parse_llm_instructions(raw, team_preset)
        assert result == {}

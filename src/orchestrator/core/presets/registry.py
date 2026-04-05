"""PresetRegistry — YAML-based preset management (stub for Phase 1)."""

from __future__ import annotations

from typing import Any

import structlog

from orchestrator.core.presets.models import AgentPreset, TeamPreset

logger = structlog.get_logger()


class PresetRegistry:
    """에이전트/팀 프리셋의 로딩, 검색, 저장을 담당한다.

    Phase 1에서는 in-memory 저장소만 사용한다.
    """

    def __init__(self, preset_dirs: list[str] | None = None) -> None:
        """
        Args:
            preset_dirs: 프리셋 YAML 검색 디렉토리 목록. None이면 ["./presets"].
        """
        self._preset_dirs = preset_dirs or ["./presets"]
        self._agent_presets: dict[str, AgentPreset] = {}
        self._team_presets: dict[str, TeamPreset] = {}

    def load_agent_preset(self, name: str) -> AgentPreset:
        """이름으로 에이전트 프리셋을 조회한다.

        Args:
            name: 프리셋 이름.

        Returns:
            프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._agent_presets:
            msg = f"Agent preset not found: {name}"
            raise KeyError(msg)
        return self._agent_presets[name]

    def load_team_preset(self, name: str) -> TeamPreset:
        """이름으로 팀 프리셋을 조회한다.

        Args:
            name: 팀 프리셋 이름.

        Returns:
            팀 프리셋 인스턴스.

        Raises:
            KeyError: 프리셋이 존재하지 않는 경우.
        """
        if name not in self._team_presets:
            msg = f"Team preset not found: {name}"
            raise KeyError(msg)
        return self._team_presets[name]

    def list_agent_presets(self) -> list[AgentPreset]:
        """등록된 모든 에이전트 프리셋을 반환한다."""
        return sorted(self._agent_presets.values(), key=lambda p: p.name)

    def list_team_presets(self) -> list[TeamPreset]:
        """등록된 모든 팀 프리셋을 반환한다."""
        return sorted(self._team_presets.values(), key=lambda p: p.name)

    def save_agent_preset(
        self,
        preset: AgentPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """에이전트 프리셋을 레지스트리에 등록한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        if not overwrite and preset.name in self._agent_presets:
            msg = f"Agent preset already exists: {preset.name}"
            raise ValueError(msg)
        self._agent_presets[preset.name] = preset
        logger.info("agent_preset_saved", name=preset.name)

    def save_team_preset(
        self,
        preset: TeamPreset,
        *,
        overwrite: bool = True,
    ) -> None:
        """팀 프리셋을 레지스트리에 등록한다.

        Args:
            preset: 저장할 프리셋.
            overwrite: 기존 프리셋 덮어쓰기 여부.

        Raises:
            ValueError: overwrite=False이고 이미 존재하는 경우.
        """
        if not overwrite and preset.name in self._team_presets:
            msg = f"Team preset already exists: {preset.name}"
            raise ValueError(msg)
        self._team_presets[preset.name] = preset
        logger.info("team_preset_saved", name=preset.name)

    def merge_preset_with_overrides(
        self,
        preset_name: str,
        overrides: dict[str, Any],
    ) -> AgentPreset:
        """기존 AgentPreset에 오버라이드를 deep merge하여 새 인스턴스를 반환한다.

        Args:
            preset_name: 기반 AgentPreset 이름.
            overrides: 오버라이드할 필드.

        Returns:
            오버라이드가 적용된 새 인스턴스 (원본 불변).

        Raises:
            KeyError: preset_name이 존재하지 않는 경우.
        """
        base = self.load_agent_preset(preset_name)
        base_dict = base.model_dump()
        merged = _deep_merge(base_dict, overrides)
        return AgentPreset.model_validate(merged)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """딕셔너리를 재귀적으로 deep merge한다.

    스칼라/리스트: 오버라이드가 대체.
    dict: 재귀적으로 merge.
    """
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
